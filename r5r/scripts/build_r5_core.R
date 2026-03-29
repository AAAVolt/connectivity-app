#!/usr/bin/env Rscript
# build_r5_core.R – Build the R5 routing network from OSM + GTFS data
#
# Reads configuration from r5r_config.yaml
# Expects OSM PBF and GTFS files in data_path

library(yaml)

config_path <- Sys.getenv("R5R_CONFIG", "/r5r/config/r5r_config.yaml")

if (!file.exists(config_path)) {
  cat(sprintf("Config file not found: %s\n", config_path))
  quit(status = 1)
}

config <- yaml::read_yaml(config_path)
data_path <- config$data_path

cat("=== R5 Network Builder ===\n")
cat(sprintf("Data path: %s\n", data_path))

dir.create(data_path, showWarnings = FALSE, recursive = TRUE)

osm_files <- list.files(data_path, pattern = "\\.pbf$")
gtfs_files <- list.files(data_path, pattern = "\\.zip$")

cat(sprintf("OSM files found:  %d\n", length(osm_files)))
cat(sprintf("GTFS files found: %d\n", length(gtfs_files)))

if (length(osm_files) == 0) {
  cat("\nRequired files not found. Place in the data directory:\n")
  cat("  1. bizkaia.osm.pbf  - OpenStreetMap extract for Bizkaia\n")
  cat("  2. *.gtfs.zip       - GTFS feed(s) for local transit operators\n")
  quit(status = 0)
}

# Build R5 network (enable when data is in place)
# library(r5r)
# r5r_core <- setup_r5(data_path = data_path)
# cat("R5 network built successfully.\n")

cat("Placeholder - provide OSM + GTFS data to build the network.\n")
