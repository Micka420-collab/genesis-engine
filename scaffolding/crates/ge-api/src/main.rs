//! ge-api — binaire principal.
//!
//! Phase 1 expose 3 surfaces :
//! - `GET  /healthz`             — liveness
//! - `GET  /readyz`              — readiness (sim chargée)
//! - `GET  /api/v1/sim/state`    — snapshot léger (tick, agents, FPS)
//! - `POST /api/v1/sim/step`     — avance d'un tick (mode dev/test)
//!
//! La sim tourne dans une task Tokio dédiée. L'état est partagé via Arc<RwLock>.

#![forbid(unsafe_code)]

use anyhow::Result;
use axum::{routing::{get, post}, Router};
use clap::Parser;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;
use tracing_subscriber::{EnvFilter, fmt};

mod routes;
mod state;
mod sim_loop;

#[derive(Parser, Debug)]
#[command(version, about = "Genesis Engine API server")]
struct Args {
    /// Adresse d'écoute.
    #[arg(long, env = "GE_BIND", default_value = "0.0.0.0:8080")]
    bind: String,
    /// Chemin du fichier de config YAML.
    #[arg(long, env = "GE_CONFIG", default_value = "config/sim-petri.yaml")]
    config: String,
    /// Chemin du journal JSONL d'événements (vide = pas de persistance).
    #[arg(long, env = "GE_JOURNAL", default_value = "events.jsonl")]
    journal: String,
    /// Override le nombre de fondateurs (0 = utiliser la config YAML).
    #[arg(long, env = "GE_FOUNDERS", default_value_t = 0)]
    founders: u32,
}

#[tokio::main]
async fn main() -> Result<()> {
    fmt()
        .with_env_filter(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .json()
        .init();

    let args = Args::parse();
    let journal = if args.journal.trim().is_empty() {
        None
    } else {
        Some(args.journal.as_str())
    };
    info!(bind = %args.bind, config = %args.config, journal = ?journal, "ge-api starting");

    let mut bootstrap = state::AppState::bootstrap(&args.config, journal)?;
    if args.founders > 0 {
        bootstrap.founder_count = args.founders;
        info!(founders = args.founders, "founder count overridden by CLI");
    }
    let app_state = Arc::new(RwLock::new(bootstrap));

    // Spawn de la boucle de sim en background.
    let sim_handle = tokio::spawn(sim_loop::run(app_state.clone()));

    let router = Router::new()
        .route("/", get(routes::dashboard))
        .route("/healthz", get(routes::healthz))
        .route("/readyz", get(routes::readyz))
        .route("/api/v1/sim/state", get(routes::sim_state))
        .route("/api/v1/sim/step", post(routes::sim_step))
        .route("/api/v1/sim/agents", get(routes::sim_agents))
        .route("/api/v1/sim/events", get(routes::sim_events))
        .route("/api/v1/sim/lineage", get(routes::sim_lineage))
        .with_state(app_state);

    let listener = tokio::net::TcpListener::bind(&args.bind).await?;
    info!("listening");
    axum::serve(listener, router).await?;

    sim_handle.abort();
    Ok(())
}
