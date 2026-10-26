ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG WHEEL_FILE
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
COPY ${WHEEL_FILE} /tmp/${WHEEL_FILE}
RUN python -m pip install --no-cache-dir "/tmp/${WHEEL_FILE}[cloud,browser,schedule,auth,anthropic]" && python -m playwright install --with-deps chromium
USER 65532:65532
ENV HOME=/tmp
CMD ["python", "-m", "atbots.platform.cloud_worker"]
