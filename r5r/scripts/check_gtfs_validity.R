# check_gtfs_validity.R – Verify the configured departure_date falls inside
# every GTFS feed's validity window before R5 builds its network.
#
# Without this check, an expired feed silently degrades to street-only
# routing: r5r still builds the network, travel_time_matrix() returns
# results, but the "transit" matrices contain only walking trips. That
# corrupts every downstream score.
#
# Usage (sourced from compute_travel_matrices.R):
#   source("/r5r/scripts/check_gtfs_validity.R")
#   check_gtfs_validity(data_path = "/data/network",
#                       reference_date = as.Date("2026-04-14"))

# Read calendar.txt or calendar_dates.txt directly out of a .zip without
# extracting to disk. Returns a data.frame with $date as Date.
.read_gtfs_dates <- function(zip_path) {
  files_in_zip <- utils::unzip(zip_path, list = TRUE)$Name

  if ("calendar.txt" %in% files_in_zip) {
    con <- unz(zip_path, "calendar.txt")
    # GTFS dates are YYYYMMDD without separators
    cal <- utils::read.csv(con, stringsAsFactors = FALSE, colClasses = "character")
    starts <- as.Date(cal$start_date, format = "%Y%m%d")
    ends   <- as.Date(cal$end_date,   format = "%Y%m%d")
    return(list(start = min(starts, na.rm = TRUE), end = max(ends, na.rm = TRUE)))
  }

  if ("calendar_dates.txt" %in% files_in_zip) {
    con <- unz(zip_path, "calendar_dates.txt")
    cd <- utils::read.csv(con, stringsAsFactors = FALSE, colClasses = "character")
    dates <- as.Date(cd$date, format = "%Y%m%d")
    return(list(start = min(dates, na.rm = TRUE), end = max(dates, na.rm = TRUE)))
  }

  stop(sprintf("GTFS feed %s has neither calendar.txt nor calendar_dates.txt",
               basename(zip_path)))
}

check_gtfs_validity <- function(data_path, reference_date) {
  if (inherits(reference_date, "character")) {
    reference_date <- as.Date(reference_date)
  }

  gtfs_files <- list.files(data_path, pattern = "\\.zip$",
                           full.names = TRUE, ignore.case = TRUE)

  if (length(gtfs_files) == 0) {
    stop(sprintf("No GTFS .zip feeds found under %s — TRANSIT routing requires at least one feed.",
                 data_path))
  }

  cat(sprintf("Checking GTFS validity for %s against %d feed(s)...\n",
              format(reference_date), length(gtfs_files)))

  problems <- character(0)
  for (zip in gtfs_files) {
    feed_name <- basename(zip)
    range <- tryCatch(.read_gtfs_dates(zip),
                      error = function(e) {
                        problems <<- c(problems,
                          sprintf("%s: %s", feed_name, conditionMessage(e)))
                        NULL
                      })
    if (is.null(range)) next

    in_window <- !is.na(range$start) && !is.na(range$end) &&
                 reference_date >= range$start && reference_date <= range$end

    cat(sprintf("  %-40s %s → %s   %s\n",
                feed_name,
                format(range$start), format(range$end),
                if (in_window) "OK" else "OUT OF RANGE"))

    if (!in_window) {
      problems <- c(problems, sprintf(
        "%s: reference_date %s is outside [%s, %s]",
        feed_name, format(reference_date),
        format(range$start), format(range$end)
      ))
    }
  }

  if (length(problems) > 0) {
    stop(paste0(
      "GTFS validity check failed for ", length(problems), " feed(s):\n  - ",
      paste(problems, collapse = "\n  - "),
      "\nUpdate r5r_config.yaml `departure_date` to a date covered by all feeds, ",
      "or fetch newer GTFS data from the operators. Refusing to proceed because ",
      "an out-of-range feed silently degrades to street-only routing."
    ))
  }

  cat("All GTFS feeds cover the reference date.\n")
  invisible(TRUE)
}
