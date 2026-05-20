//! Genesis Studio — scientific world generation launcher.
//!
//! Think Epic Games Launcher, but for scientific experiments. Drop a YAML
//! scenario into `scenarios/`, run `genesis-studio list` to see them,
//! `genesis-studio run my_scenario.yaml --out runs/` to execute, and
//! collect the reproducible artefacts + FAIR manifest.
//!
//! Usage:
//!
//! ```text
//!   genesis-studio info                  # engine + system info
//!   genesis-studio constants              # show built-in physical constants
//!   genesis-studio list <dir>             # list YAML scenarios
//!   genesis-studio validate <file.yaml>   # parse + validate, don't run
//!   genesis-studio run <file.yaml> -o RUNS
//!   genesis-studio init <name>            # create a starter scenario
//! ```

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use genesis_scenario::{run_scenario, ProgressEvent, Scenario};
use indicatif::{ProgressBar, ProgressStyle};
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "genesis-studio", version, about, long_about = None)]
struct Cli {
    /// Verbose logging.
    #[arg(short, long, global = true)]
    verbose: bool,

    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Show engine and platform information.
    Info,
    /// Print the built-in physical constants table.
    Constants,
    /// List scenarios in a directory.
    List {
        /// Directory to scan (default: ./scenarios)
        #[arg(default_value = "./scenarios")]
        dir: PathBuf,
    },
    /// Parse + validate a scenario without running it.
    Validate {
        /// Scenario YAML file.
        file: PathBuf,
    },
    /// Run a scenario.
    Run {
        /// Scenario YAML file.
        file: PathBuf,
        /// Output directory.
        #[arg(short = 'o', long, default_value = "./runs")]
        out: PathBuf,
    },
    /// Create a starter scenario file.
    Init {
        /// Name of the scenario (used as base filename).
        name: String,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    let level = if cli.verbose { "debug" } else { "info" };
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::new(format!("genesis_studio={level},genesis_scenario={level}")))
        .compact()
        .init();

    match cli.command {
        Command::Info => cmd_info(),
        Command::Constants => cmd_constants(),
        Command::List { dir } => cmd_list(&dir),
        Command::Validate { file } => cmd_validate(&file),
        Command::Run { file, out } => cmd_run(&file, &out),
        Command::Init { name } => cmd_init(&name),
    }
}

fn cmd_info() -> Result<()> {
    println!("Genesis Studio v{}", env!("CARGO_PKG_VERSION"));
    println!("Engine: genesis-engine native (Rust)");
    println!(
        "Built: {} on {}",
        env!("CARGO_PKG_VERSION"),
        std::env::consts::OS
    );
    println!("Arch:  {}", std::env::consts::ARCH);
    Ok(())
}

fn cmd_constants() -> Result<()> {
    use genesis_physics::*;
    println!("Built-in physical constants (CODATA 2018):");
    println!("  G (gravitational)       = {:e} N·m²/kg²", G);
    println!("  c (speed of light)      = {} m/s", SPEED_OF_LIGHT.value());
    println!("  h (Planck)              = {:e} J·s", PLANCK);
    println!("  k_B (Boltzmann)         = {:e} J/K", BOLTZMANN);
    println!("  N_A (Avogadro)          = {:e} 1/mol", AVOGADRO);
    println!("  R (gas constant)        = {} J/(mol·K)", GAS_R);
    println!("  σ (Stefan-Boltzmann)    = {:e} W/(m²·K⁴)", STEFAN_BOLTZMANN);
    println!("  g_Earth                 = {} m/s²", G_EARTH.value());
    println!("  R_Earth                 = {} m", EARTH_RADIUS.value());
    println!("  M_Earth                 = {:e} kg", EARTH_MASS.value());
    println!("  Solar constant          = {} W/m²", SOLAR_CONSTANT.value());
    println!("  Std. pressure (1 atm)   = {} Pa", STANDARD_PRESSURE.value());
    println!("  Water triple point      = {} K", WATER_TRIPLE.value());
    println!("  Air c_p                 = {} J/(kg·K)", AIR_CP.value());
    println!("  Water c_p               = {} J/(kg·K)", WATER_CP.value());
    println!("  Sidereal day            = {} s", SIDEREAL_DAY.value());
    println!("  Tropical year           = {} s", TROPICAL_YEAR.value());
    Ok(())
}

fn cmd_list(dir: &std::path::Path) -> Result<()> {
    if !dir.exists() {
        println!("(no scenarios directory at {})", dir.display());
        return Ok(());
    }
    let mut found = 0;
    for entry in std::fs::read_dir(dir).with_context(|| format!("reading {}", dir.display()))? {
        let entry = entry?;
        let p = entry.path();
        if p.extension().map(|e| e == "yaml" || e == "yml").unwrap_or(false) {
            found += 1;
            match Scenario::load(&p) {
                Ok(s) => println!("  {:<40}  {}", p.file_name().unwrap().to_string_lossy(), s.name),
                Err(e) => println!("  {:<40}  [invalid: {}]", p.file_name().unwrap().to_string_lossy(), e),
            }
        }
    }
    if found == 0 {
        println!("(no .yaml/.yml scenarios found in {})", dir.display());
    }
    Ok(())
}

fn cmd_validate(file: &std::path::Path) -> Result<()> {
    let s = Scenario::load(file).with_context(|| format!("loading {}", file.display()))?;
    println!("Scenario '{}' validated.", s.name);
    println!("  authors: {}", s.metadata.authors.join(", "));
    println!("  license: {}", s.metadata.license);
    println!("  extent:  {} chunks", s.world.extent_chunks.count());
    println!("  ticks:   {}", s.experiment.ticks);
    println!(
        "  duration: {:.1} sim-days",
        (s.experiment.ticks as f64 * s.experiment.dt_seconds) / 86_400.0
    );
    Ok(())
}

fn cmd_run(file: &std::path::Path, out: &std::path::Path) -> Result<()> {
    let scenario = Scenario::load(file).with_context(|| format!("loading {}", file.display()))?;
    let stamp = chrono::Utc::now().format("%Y%m%dT%H%M%SZ").to_string();
    let safe_name: String = scenario
        .name
        .chars()
        .map(|c| if c.is_alphanumeric() || c == '-' || c == '_' { c } else { '_' })
        .collect();
    let run_dir = out.join(format!("{}-{}", safe_name, stamp));
    std::fs::create_dir_all(&run_dir)?;
    println!("→ output: {}", run_dir.display());

    let pb = ProgressBar::new(scenario.experiment.ticks);
    pb.set_style(
        ProgressStyle::with_template("{elapsed_precise} [{wide_bar}] {pos:>6}/{len:6} ticks ({eta})")
            .unwrap()
            .progress_chars("=>-"),
    );

    let manifest = run_scenario(&scenario, &run_dir, |ev| match ev {
        ProgressEvent::Start { total_ticks } => {
            println!("▶ starting {} ticks", total_ticks);
        }
        ProgressEvent::Tick { tick, total: _ } => {
            pb.set_position(tick + 1);
        }
        ProgressEvent::Measurement { name, tick, value } => {
            tracing::debug!(name, tick, value, "measurement");
        }
        ProgressEvent::Done(m) => {
            pb.finish_with_message("done");
            println!(
                "✓ run {} finished in {:.2}s — {} measurements over {} chunks",
                m.run_id, m.summary.wall_seconds, m.summary.measurements_recorded, m.summary.chunks
            );
        }
    })?;

    println!("Manifest:");
    println!("  scenario_hash: {}", manifest.scenario_hash);
    for a in &manifest.artefacts {
        println!(
            "  artefact: {} ({} bytes, blake3 {})",
            a.path, a.size_bytes, &a.blake3[..16]
        );
    }
    Ok(())
}

fn cmd_init(name: &str) -> Result<()> {
    let path = std::path::PathBuf::from(format!("{name}.yaml"));
    if path.exists() {
        anyhow::bail!("{} already exists", path.display());
    }
    let starter = format!(
r#"name: "{name}"
description: "Edit me — describe the experiment in one paragraph."
version: "1"
metadata:
  authors: ["You"]
  license: "Apache-2.0"
  keywords: ["genesis", "demo"]
world:
  seed: 42
  extent_chunks: {{ min_cx: 0, max_cx: 7, min_cy: 0, max_cy: 7 }}
  climate:
    t_equator_c: 28.0
    t_pole_c: -25.0
    continentality: 0.6
experiment:
  ticks: 100
  dt_seconds: 86400.0
measurements:
  - kind: MeanTemperature
    every_ticks: 10
  - kind: TotalPrecipitation
    every_ticks: 10
  - kind: BiomeHistogram
    every_ticks: 25
  - kind: MeanWindSpeed
    every_ticks: 10
exports:
  - format: Csv
    path: out.csv
  - format: Json
    path: out.json
"#,
        name = name
    );
    std::fs::write(&path, starter)?;
    println!("Wrote {}", path.display());
    Ok(())
}
