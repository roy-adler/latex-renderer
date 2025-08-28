# ---------- LaTeX rendering service with LaTeXmk ----------
FROM ubuntu:22.04

# Install TeX Live + latexmk with comprehensive packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl python3 python3-pip python3-venv unzip xz-utils \
    latexmk texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    texlive-lang-german texlive-lang-english texlive-science texlive-publishers \
    texlive-lang-other texlive-lang-european texlive-extra-utils texlive-bibtex-extra \
    texlive-full biber make ghostscript \
    && rm -rf /var/lib/apt/lists/*

# App
WORKDIR /app
COPY requirements.txt /app/

# Create virtual environment and install dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app

# Security: run as non-root
RUN useradd -m runner
USER runner

EXPOSE 8000
CMD ["/opt/venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]