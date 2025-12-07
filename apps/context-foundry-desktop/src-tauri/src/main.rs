//! Context Foundry Desktop - Main Entry Point
//!
//! This is the main entry point for the Tauri desktop application.
//! It initializes the application and starts the event loop.

// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    context_foundry_desktop_lib::run()
}
