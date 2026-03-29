#!/usr/bin/env Rscript
# compute_travel_matrices.R – Compute travel-time matrices using r5r
#
# Reads configuration from r5r_config.yaml
# Expects a built R5 network in data_path
# Writes travel time matrices to output_path

library(yaml)

config_path <- Sys.getenv("R5R_CONFIG", "/r5r/config/r5r_config.yaml")

if (!file.exists(config_path)) {
  cat(sprintf("Config file not found: %s\n", config_path))
  quit(status = 1)
}

config <- yaml::read_yaml(config_path)

cat("=== Bizkaia Travel Time Matrix Computation ===\n")
cat(sprintf("Modes:           %s\n", paste(config$modes, collapse = ", ")))
cat(sprintf("Time window:     %s - %s\n", config$departure_time_start, config$departure_time_end))
cat(sprintf("Max travel time: %d min\n", config$max_travel_time_minutes))

data_path <- config$data_path
output_path <- config$output_path

dir.create(output_path, showWarnings = FALSE, recursive = TRUE)

osm_files <- list.files(data_path, pattern = "\\.pbf$", full.names = TRUE)
if (length(osm_files) == 0) {
  cat("ERROR: No .pbf file found. Run build_r5_core.R first.\n")
  quit(status = 1)
}

cat(sprintf("OSM: %s\n", basename(osm_files[1])))

# Compute travel time matrix (enable when data + origins/destinations are ready)
# library(r5r)
# library(sf)
# library(data.table)
#
# r5r_core <- setup_r5(data_path = data_path)
# origins <- st_read(file.path(data_path, "origins.gpkg"))
# destinations <- st_read(file.path(data_path, "destinations.gpkg"))
#
# ttm <- travel_time_matrix(
#   r5r_core,
#   origins = origins,
#   destinations = destinations,
#   mode = config$modes,
#   departure_datetime = as.POSIXct(config$departure_datetime),
#   max_trip_duration = config$max_travel_time_minutes,
#   time_window = config$time_window_minutes,
#   percentiles = config$percentiles
# )
#
# library(arrow)
# output_file <- file.path(output_path, "ttm.parquet")
# write_parquet(ttm, output_file)
# cat(sprintf("Written: %s (%d rows)\n", output_file, nrow(ttm)))

cat("Placeholder - provide OSM + GTFS data to compute matrices.\n")
