# Stage 1: Build environment
FROM python:3.12-alpine AS builder
RUN apk add --no-cache gcc musl-dev libffi-dev git
WORKDIR /app
COPY requirements.txt demo-requirements.txt pyproject.toml src /app/
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    pip install --no-cache-dir --prefix=/install -r demo-requirements.txt
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime environment
FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache libffi
COPY --from=builder /install /usr/local
COPY . /app/
# Create temp/dict folder to inject dictionary releases via directory mapping
RUN mkdir -p /app/temp/dict
EXPOSE 7860

# run the Gradio demo
ENTRYPOINT ["python", "examples/demo_gradio.py"]