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

# Symlink to a canonical path so JAVA_HOME is architecture-independent
RUN ln -sf /usr/lib/jvm/temurin-21-jdk-* /usr/lib/jvm/temurin-21-jdk
ENV JAVA_HOME=/usr/lib/jvm/temurin-21-jdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Configure Java for R (required by rJava / r5r)
RUN R CMD javareconf

# Pin R package versions for reproducible builds (update manually when needed)
RUN R -e " \
  install.packages('remotes', repos='https://cloud.r-project.org/'); \
  remotes::install_version('rJava',     version='1.0-11',  repos='https://cloud.r-project.org/'); \
  remotes::install_version('sf',        version='1.0-19',  repos='https://cloud.r-project.org/'); \
  remotes::install_version('data.table',version='1.16.4',  repos='https://cloud.r-project.org/'); \
  remotes::install_version('yaml',      version='2.3.10',  repos='https://cloud.r-project.org/'); \
  remotes::install_version('arrow',     version='18.1.0',  repos='https://cloud.r-project.org/'); \
  remotes::install_version('r5r',       version='2.3',     repos='https://cloud.r-project.org/'); \
"

WORKDIR /r5r
COPY r5r/scripts/ /r5r/scripts/
COPY r5r/config/ /r5r/config/

CMD ["Rscript", "/r5r/scripts/compute_travel_matrices.R"]
