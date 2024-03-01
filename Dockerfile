FROM python:3-alpine

LABEL name="dilla-schemas-validator"
LABEL maintainer="pierre@dilla.io"
LABEL version="1.0.0"
LABEL description="Dilla schemas validator for project https://dilla.io"
LABEL org.label-schema.schema-version="1.0.0"
LABEL org.label-schema.name="dillaio/schemas"
LABEL org.label-schema.description="Dilla schemas validator for project https://dilla.io"
LABEL org.label-schema.url="https://gitlab.com/dilla-io/schemas"
LABEL org.label-schema.vcs-url="https://gitlab.com/dilla-io/schemas.git"
LABEL org.label-schema.vendor="dilla.io"

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.json ./
COPY *.py ./

ENTRYPOINT [ "python", "./validator.py" ]
