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

fn spawn_backend() -> Option<Child> {
    // python3 first (Linux/macOS), then python (Windows / venvs)
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
