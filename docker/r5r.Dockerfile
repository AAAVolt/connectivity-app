# Build context: repo root (.)
FROM rocker/r-ver:4.3.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libudunits2-dev \
    libssl-dev \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN R -e "install.packages(c('r5r', 'sf', 'data.table', 'yaml', 'arrow'), repos='https://cloud.r-project.org/')"

WORKDIR /r5r
COPY r5r/scripts/ /r5r/scripts/
COPY r5r/config/ /r5r/config/

CMD ["Rscript", "/r5r/scripts/compute_travel_matrices.R"]
