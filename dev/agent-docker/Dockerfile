FROM python:3.11-slim

WORKDIR /opt/lab_guardian

# System deps for psutil / netifaces / pyudev
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libudev-dev && \
    rm -rf /var/lib/apt/lists/*

COPY lab_guardian/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lab_guardian/ .
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["lab_guardian"]
CMD ["join", "-v"]
