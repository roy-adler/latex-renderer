# ---------- Option A: Tectonic-first image (small, fast) ----------
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 python3-pip unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic
RUN curl -L https://github.com/tectonic-typesetting/tectonic/releases/latest/download/tectonic-x86_64-unknown-linux-gnu.tar.xz \
  | tar -xJ -C /usr/local/bin --strip-components=1 ./tectonic

# (Optional) Install a minimal TeX Live + latexmk for fallback engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    latexmk texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    biber make ghostscript \
    && rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY app /app
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# Security: run as non-root
RUN useradd -m runner
USER runner

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    