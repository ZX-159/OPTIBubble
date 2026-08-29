// OPTIBubble — Tauri 2 desktop shell.
//
// The entire UI + OMR engine lives in the bundled Python server
// (`main.py`, Flask + OpenCV). This shell:
//   1. spawns `python main.py --no-browser` if the backend isn't already up,
//   2. waits for 127.0.0.1:5000 to accept connections,
//   3. opens a native window pointed at the local web app,
//   4. kills the backend when the window closes.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;

use tauri::Manager;

const HOST: &str = "127.0.0.1";
const PORT: u16 = 5000;

fn backend_up() -> bool {
    TcpStream::connect((HOST, PORT)).is_ok()
}

fn bundled_engine() -> Option<std::path::PathBuf> {
    // release installers ship the frozen engine under resources/engine/
    let exe = std::env::current_exe().ok()?;
    let name = if cfg!(windows) { "optibubble-engine.exe" } else { "optibubble-engine" };
    let exe_dir = exe.parent()?;
    [
        exe_dir.join("engine").join(name),            // windows / linux bundle
        exe_dir.join("../Resources/engine").join(name), // macOS .app bundle
        exe_dir.join("../../Resources/engine").join(name),
        exe_dir.join(name),                           // portable layouts
    ]
    .into_iter()
    .find(|p| p.exists())
}

fn spawn_backend() -> Option<Child> {
    // 1 · the frozen engine bundled with the installer (no Python needed)
    if let Some(engine) = bundled_engine() {
        if let Ok(child) = Command::new(&engine).arg("--no-browser").spawn() {
            return Some(child);
        }
    }
    // 2 · fall back to a system python (developer machines)
    for exe in ["python3", "python"] {
        if let Ok(child) = Command::new(exe)
            .args(["main.py", "--no-browser"])
            .current_dir("..")          // src-tauri/ → project root
            .spawn()
        {
            return Some(child);
        }
    }
    None
}

fn main() {
    let child: Option<Child> = if !backend_up() {
        let c = spawn_backend();
        // wait up to 30 s for the engine (first import of cv2 can be slow)
        for _ in 0..150 {
            if backend_up() {
                break;
            }
            std::thread::sleep(Duration::from_millis(200));
        }
        c
    } else {
        None
    };

    let managed = Mutex::new(child);

    let app = tauri::Builder::default()
        .manage(managed)
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
