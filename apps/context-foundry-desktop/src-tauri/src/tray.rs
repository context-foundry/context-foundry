//! System Tray Module
//!
//! Provides system tray icon and menu functionality for the desktop app.

use tauri::{
    App, AppHandle, Manager, Emitter,
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState},
};
use log::{info, error};

/// Setup the system tray icon and menu
/// Note: System tray is optional and requires a valid icon to be configured.
/// If no icon is available, the tray setup is skipped.
pub fn setup_tray(app: &App) -> Result<(), Box<dyn std::error::Error>> {
    info!("Setting up system tray...");

    // Check if we have an icon available
    let icon = match app.default_window_icon() {
        Some(icon) => icon.clone(),
        None => {
            info!("No default icon available, skipping system tray setup");
            return Ok(());
        }
    };

    // Create menu items
    let show = MenuItem::with_id(app, "show", "Show Dashboard", true, None::<&str>)?;
    let status = MenuItem::with_id(app, "status", "Daemon: Checking...", false, None::<&str>)?;
    let separator = MenuItem::with_id(app, "sep1", "---", false, None::<&str>)?;
    let start_daemon = MenuItem::with_id(app, "start_daemon", "Start Daemon", true, None::<&str>)?;
    let stop_daemon = MenuItem::with_id(app, "stop_daemon", "Stop Daemon", true, None::<&str>)?;
    let restart_daemon = MenuItem::with_id(app, "restart_daemon", "Restart Daemon", true, None::<&str>)?;
    let separator2 = MenuItem::with_id(app, "sep2", "---", false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    // Build menu
    let menu = Menu::with_items(app, &[
        &show,
        &status,
        &separator,
        &start_daemon,
        &stop_daemon,
        &restart_daemon,
        &separator2,
        &quit,
    ])?;

    // Build tray icon
    let _tray = TrayIconBuilder::new()
        .icon(icon)
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| {
            handle_menu_event(app, &event.id.0);
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                // Show main window on left click
                if let Some(window) = tray.app_handle().get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    info!("System tray setup complete");
    Ok(())
}

/// Handle tray menu item clicks
fn handle_menu_event(app: &AppHandle, id: &str) {
    match id {
        "show" => {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
        "start_daemon" => {
            info!("Tray: Start daemon requested");
            let handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state: tauri::State<'_, crate::AppState> = handle.state();
                let mut manager = state.daemon_manager.lock().await;
                match manager.ensure_running().await {
                    Ok(status) => {
                        let _ = handle.emit("daemon-status", &status);
                    }
                    Err(e) => {
                        error!("Failed to start daemon: {}", e);
                        let _ = handle.emit("daemon-error", e.to_string());
                    }
                }
            });
        }
        "stop_daemon" => {
            info!("Tray: Stop daemon requested");
            let handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state: tauri::State<'_, crate::AppState> = handle.state();
                let mut manager = state.daemon_manager.lock().await;
                match manager.stop().await {
                    Ok(_) => {
                        let _ = handle.emit("daemon-status", &crate::daemon::DaemonStatus::default());
                    }
                    Err(e) => {
                        error!("Failed to stop daemon: {}", e);
                        let _ = handle.emit("daemon-error", e.to_string());
                    }
                }
            });
        }
        "restart_daemon" => {
            info!("Tray: Restart daemon requested");
            let handle = app.clone();
            tauri::async_runtime::spawn(async move {
                let state: tauri::State<'_, crate::AppState> = handle.state();
                let mut manager = state.daemon_manager.lock().await;
                match manager.restart().await {
                    Ok(status) => {
                        let _ = handle.emit("daemon-status", &status);
                    }
                    Err(e) => {
                        error!("Failed to restart daemon: {}", e);
                        let _ = handle.emit("daemon-error", e.to_string());
                    }
                }
            });
        }
        "quit" => {
            info!("Tray: Quit requested");
            std::process::exit(0);
        }
        _ => {}
    }
}
