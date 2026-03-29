# Build context: repo root (.)
FROM rocker/r-ver:4.3.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libudunits2-dev \
    libssl-dev \
    libcurl4-openssl-dev \
    libbz2-dev \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Eclipse Temurin JDK 21 (required by r5r >= 2.3)
RUN wget -qO- https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /usr/share/keyrings/adoptium.asc > /dev/null \
    && echo "deb [signed-by=/usr/share/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(. /etc/os-release && echo $VERSION_CODENAME) main" \
    | tee /etc/apt/sources.list.d/adoptium.list \
    && apt-get update && apt-get install -y --no-install-recommends temurin-21-jdk \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/temurin-21-jdk-arm64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Configure Java for R (required by rJava / r5r)
RUN R CMD javareconf

RUN R -e "install.packages(c('rJava', 'sf', 'data.table', 'yaml', 'arrow', 'r5r'), repos='https://cloud.r-project.org/')"

WORKDIR /r5r
COPY r5r/scripts/ /r5r/scripts/
COPY r5r/config/ /r5r/config/

CMD ["Rscript", "/r5r/scripts/compute_travel_matrices.R"]
