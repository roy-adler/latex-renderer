# ---------- Option A: Tectonic-first image (small, fast) ----------
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 python3-pip python3-venv unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic - try multiple approaches
RUN curl -L https://github.com/tectonic-typesetting/tectonic/releases/latest/download/tectonic-x86_64-unknown-linux-gnu.tar.xz \
    -o /tmp/tectonic.tar.xz \
    && tar -xf /tmp/tectonic.tar.xz -C /tmp \
    && find /tmp -name "tectonic" -executable -exec mv {} /usr/local/bin/ \; \
    && rm -rf /tmp/* \
    || echo "Tectonic installation failed, will use TeX Live fallback"

# Install TeX Live + latexmk for fallback engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    latexmk texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    biber make ghostscript \
    && rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY app /app
COPY requirements.txt /app/

# Create virtual environment and install dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Security: run as non-root
RUN useradd -m runner
USER runner

EXPOSE 8000
CMD ["/opt/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]