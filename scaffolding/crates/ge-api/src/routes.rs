//! Handlers HTTP.

use crate::sim_loop::step_once;
use crate::state::{AgentView, AppState, SimSnapshot};
use axum::{
    extract::{Query, State},
    http::{header, StatusCode},
    response::IntoResponse,
    Json,
};
use ge_ann::Event;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

/// GET /healthz — toujours 200 si le process est vivant.
pub async fn healthz() -> &'static str {
    "ok"
}

/// GET /readyz — 200 si la sim est initialisée, 503 sinon.
pub async fn readyz(State(s): State<Arc<RwLock<AppState>>>) -> impl IntoResponse {
    let g = s.read().await;
    if g.ready {
        (StatusCode::OK, "ready")
    } else {
        (StatusCode::SERVICE_UNAVAILABLE, "not ready")
    }
}

/// GET /api/v1/sim/state — snapshot léger.
pub async fn sim_state(State(s): State<Arc<RwLock<AppState>>>) -> Json<SimSnapshot> {
    let g = s.read().await;
    Json(g.snapshot())
}

/// POST /api/v1/sim/step — exécute un tick complet (mode dev/test).
pub async fn sim_step(State(s): State<Arc<RwLock<AppState>>>) -> Json<SimSnapshot> {
    let mut g = s.write().await;
    if !g.bootstrapped {
        g.spawn_initial();
    }
    step_once(&mut g);
    Json(g.snapshot())
}

/// Query string : ?limit=N (défaut 1000, max 10 000).
#[derive(Deserialize)]
pub struct AgentsQuery {
    #[serde(default)]
    limit: Option<usize>,
}

/// GET /api/v1/sim/agents — liste les agents vivants/morts (limit configurable).
pub async fn sim_agents(
    State(s): State<Arc<RwLock<AppState>>>,
    Query(q): Query<AgentsQuery>,
) -> Json<Vec<AgentView>> {
    let limit = q.limit.unwrap_or(1000).min(10_000);
    let mut g = s.write().await;
    let agents = g.list_agents(limit);
    Json(agents)
}

/// Query string : ?limit=N (défaut 200, max 1024).
#[derive(Deserialize)]
pub struct EventsQuery {
    #[serde(default)]
    limit: Option<usize>,
    /// Filtre par type ("Birth", "Death", etc.). Insensible à la casse.
    #[serde(default)]
    kind: Option<String>,
}

/// GET /api/v1/sim/events — buffer borné des derniers événements.
pub async fn sim_events(
    State(s): State<Arc<RwLock<AppState>>>,
    Query(q): Query<EventsQuery>,
) -> Json<Vec<Event>> {
    let limit = q.limit.unwrap_or(200).min(1024);
    let g = s.read().await;
    let kind = q.kind.as_deref().map(|k| k.to_ascii_lowercase());
    let mut out: Vec<Event> = g
        .recent_events
        .iter()
        .rev()
        .filter(|e| match kind.as_deref() {
            None => true,
            Some(k) => format!("{:?}", e.kind).to_ascii_lowercase() == k,
        })
        .take(limit)
        .cloned()
        .collect();
    out.reverse();
    Json(out)
}

#[derive(Serialize)]
pub struct LineageStats {
    pub max_generation: u32,
    pub births_total: u64,
    pub deaths_total: u32,
}

/// GET /api/v1/sim/lineage — stats agrégées sur la lignée.
pub async fn sim_lineage(State(s): State<Arc<RwLock<AppState>>>) -> Json<LineageStats> {
    let g = s.read().await;
    Json(LineageStats {
        max_generation: g.max_generation,
        births_total: g.births_total,
        deaths_total: g.agents_dead,
    })
}

/// GET / — sert le dashboard HTML (statique embarqué).
pub async fn dashboard() -> impl IntoResponse {
    let body = include_str!("../assets/dashboard.html");
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/html; charset=utf-8")],
        body,
    )
}
