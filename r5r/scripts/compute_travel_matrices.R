#!/usr/bin/env Rscript
# compute_travel_matrices.R – Compute travel-time matrices using r5r
#
# Reads configuration from r5r_config.yaml.
# Iterates over every 30-minute departure slot (00:00 – 23:30) and
# writes one Parquet file per (mode, slot):
#   ttm_{mode}_{HHMM}.parquet   e.g. ttm_transit_0830.parquet
#
# Expects a built R5 network in data_path.

library(yaml)

config_path <- Sys.getenv("R5R_CONFIG", "/r5r/config/r5r_config.yaml")

if (!file.exists(config_path)) {
  cat(sprintf("Config file not found: %s\n", config_path))
  quit(status = 1)
}

config <- yaml::read_yaml(config_path)

# Allocate Java memory before loading r5r
options(java.parameters = sprintf("-Xmx%dM", config$max_memory_mb))

cat("=== Bizkaia Travel Time Matrix Computation ===\n")
cat(sprintf("Modes:           %s\n", paste(config$modes, collapse = ", ")))
cat(sprintf("Slot interval:   %d min\n", config$departure_slot_interval_minutes))
cat(sprintf("Time window:     %d min per slot\n", config$time_window_minutes))
cat(sprintf("Max travel time: %d min\n", config$max_travel_time_minutes))
cat(sprintf("Java memory:     %d MB\n", config$max_memory_mb))

data_path <- config$data_path
output_path <- config$output_path

dir.create(output_path, showWarnings = FALSE, recursive = TRUE)

osm_files <- list.files(data_path, pattern = "\\.pbf$", full.names = TRUE)
if (length(osm_files) == 0) {
  cat("ERROR: No .pbf file found. Run build_r5_core.R first.\n")
  quit(status = 1)
}

cat(sprintf("OSM: %s\n", basename(osm_files[1])))

library(r5r)
library(sf)
library(data.table)
library(arrow)

# Read origins and destinations from CSV (id, lon, lat)
origins_path <- as.character(config$origins_csv)
destinations_path <- as.character(config$destinations_csv)
origins <- fread(origins_path)
destinations <- fread(destinations_path)

cat(sprintf("Origins:      %d points\n", nrow(origins)))
cat(sprintf("Destinations: %d points\n", nrow(destinations)))

# Build/load the R5 network (Java)
cat("Building R5 network (this may take a few minutes on first run)...\n")
r5r_core <- r5r::build_network(data_path = data_path, verbose = FALSE)

# ── Generate departure time slots ──
ref_date <- as.Date(config$departure_date)
start_parts <- as.integer(strsplit(config$departure_time_start, ":")[[1]])
end_parts   <- as.integer(strsplit(config$departure_time_end, ":")[[1]])

start_min <- start_parts[1] * 60 + start_parts[2]
end_min   <- end_parts[1] * 60 + end_parts[2]
interval  <- config$departure_slot_interval_minutes

slot_minutes <- seq(start_min, end_min, by = interval)

cat(sprintf("Departure slots: %d (from %s to %s every %d min)\n",
    length(slot_minutes), config$departure_time_start,
    config$departure_time_end, interval))

# ── Compute travel time matrices per (mode, slot) ──
for (mode in config$modes) {
  if (mode == "WALK") {
    mode_vec <- "WALK"
  } else {
    mode_vec <- c("WALK", "TRANSIT")
  }

  for (slot_m in slot_minutes) {
    hh <- slot_m %/% 60
    mm <- slot_m %% 60
    slot_label <- sprintf("%02d%02d", hh, mm)
    slot_time  <- sprintf("%02d:%02d", hh, mm)

    departure_dt <- as.POSIXct(
      sprintf("%s %s:00", config$departure_date, slot_time),
      tz = "Europe/Madrid"
    )

    cat(sprintf("\n--- %s @ %s ---\n", mode, slot_time))

    tryCatch({
      ttm <- travel_time_matrix(
        r5r_core,
        origins = origins,
        destinations = destinations,
        mode = mode_vec,
        departure_datetime = departure_dt,
        max_trip_duration = config$max_travel_time_minutes,
        time_window = config$time_window_minutes,
        percentiles = as.integer(config$percentiles),
        walk_speed = config$walk_speed_kmh,
        max_walk_time = as.integer(
          config$max_walk_distance_m / (config$walk_speed_kmh * 1000 / 60)
        ),
        verbose = FALSE,
        progress = TRUE
      )

      cat(sprintf("  Rows: %d\n", nrow(ttm)))

      output_file <- file.path(
        output_path,
        sprintf("ttm_%s_%s.parquet", tolower(mode), slot_label)
      )
      write_parquet(ttm, output_file)
      cat(sprintf("  Written: %s\n", output_file))
    }, error = function(e) {
      cat(sprintf("  ERROR computing %s @ %s: %s\n",
          mode, slot_time, conditionMessage(e)))
      cat("  Skipping this slot and continuing...\n")
    })
  }
}

stop_r5(r5r_core)
cat("\nDone.\n")
