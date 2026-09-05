// OPTIBubble — Tauri 2 desktop shell.
//
// The entire UI + OMR engine lives in the bundled Python server
// (`main.py`, Flask + OpenCV). This shell:
//   1. spawns `python main.py --no-browser` if the backend isn't already up,
//   2. waits for the engine's HTTP port to accept connections,
//   3. opens a native window pointed at the local web app,
//   4. kills the backend when the window closes.
//
// The engine deliberately falls back to 5001..5009 when the configured port
// (default 5000) is already in use (e.g. macOS AirPlay Receiver). It publishes
// the port it actually bound to a temp file via `--port-file`; this shell reads
// that file so the native window is never pointed at a dead port.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

const HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 5000;

/// Where the engine publishes the port it actually bound. The shell passes this
/// path to `python main.py --port-file …`; reading it avoids the hard-coded
/// 5000 assumption that breaks whenever the engine falls back.
fn port_file() -> PathBuf {
    std::env::temp_dir().join("optibubble-port.txt")
}

fn read_port_from_file() -> Option<u16> {
    std::fs::read_to_string(port_file())
        .ok()?
        .trim()
        .parse()
        .ok()
}

fn backend_up(port: u16) -> bool {
    TcpStream::connect((HOST, port)).is_ok()
}

fn bundled_engine() -> Option<std::path::PathBuf> {
    // release installers ship the frozen engine under resources/engine/
    let exe = std::env::current_exe().ok()?;
    let name = if cfg!(windows) { "optibubble-engine.exe" } else { "optibubble-engine" };
    let exe_dir = exe.parent()?;
    [
        exe_dir.join("engine").join(name),               // windows / linux bundle
        exe_dir.join("../Resources/engine").join(name),  // macOS .app bundle
        exe_dir.join("../../Resources/engine").join(name),
        exe_dir.join(name),                              // portable layouts
    ]
    .into_iter()
    .find(|p| p.exists())
}

fn spawn_backend() -> Option<Child> {
    // 1 · the frozen engine bundled with the installer (no Python needed)
    if let Some(engine) = bundled_engine() {
        if let Ok(child) = Command::new(&engine)
            .args(["--no-browser", "--port-file"])
            .arg(port_file())
            .spawn()
        {
            return Some(child);
        }
    }
    // 2 · fall back to a system python (developer machines)
    for exe in ["python3", "python"] {
        if let Ok(child) = Command::new(exe)
            .args(["main.py", "--no-browser", "--port-file"])
            .arg(port_file())
            .current_dir("..")          // src-tauri/ → project root
            .spawn()
        {
            return Some(child);
        }
    }
    None
}

/// Wait for the backend, returning the port it is actually serving on.
/// Prefers the port the engine published; falls back to probing the default.
fn wait_for_backend(timeout: Duration) -> u16 {
    let start = Instant::now();
    loop {
        if let Some(p) = read_port_from_file() {
            if backend_up(p) {
                return p;
            }
        }
        if backend_up(DEFAULT_PORT) {
            return DEFAULT_PORT;
        }
        if start.elapsed() >= timeout {
            break;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    DEFAULT_PORT
}

/// Build the main webview at the *actual* serving port (not hard-coded 5000).
fn build_window(app: &tauri::App, port: u16) -> tauri::Result<()> {
    let url_str = format!("http://{}:{}/", HOST, port);
    // The URL is built from constants, so parsing cannot fail in practice.
    let url = url::Url::parse(&url_str).expect("valid local URL");
    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
        .title("OPTIBubble \u{2014} Scan. Grade. Done.")
        .inner_size(1300.0, 860.0)
        .min_inner_size(1020.0, 700.0)
        .center()
        .build()?;
    Ok(())
}

fn main() {
    // clear any stale port file from a previous run
    let _ = std::fs::remove_file(port_file());

    let child: Option<Child> = if !backend_up(DEFAULT_PORT) {
        let c = spawn_backend();
        // wait up to 30 s for the engine (first import of cv2 can be slow)
        let _ = wait_for_backend(Duration::from_secs(30));
        c
    } else {
        None
    };

    // The engine publishes the port it actually bound; read it once and open
    // the window there (never hard-code 5000, which the engine may have
    // fallen back from on a busy machine).
    let port = wait_for_backend(Duration::from_secs(30));
    eprintln!("OPTIBubble engine serving on http://{}:{}/", HOST, port);

    let managed = Mutex::new(child);

    let app = tauri::Builder::default()
        .manage(managed)
        .setup(move |app| {
            build_window(app, port)?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building OPTIBubble");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(mut child) = app_handle
                .state::<Mutex<Option<Child>>>()
                .lock()
                .ok()
                .and_then(|mut guard| guard.take())
            {
                let _ = child.kill();
            }
        }
    });
}
