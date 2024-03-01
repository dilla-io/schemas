# Dilla Schemas

## definitions.schema.json

### A Web design system description format

Each design system is fully and statically described with structured data, easily writable in JSON or YAML. Each design system can contains UI components, but also styles utilities, themes, CSS variables and examples.

Those descriptions are used by the rendering service, and exposed by the Definition API.

Example:

```yaml
id: card
label: Card
group: Content
slots:
  body:
    label: Card body
```

## renderable.schema.json

### A renderable payload format

An universal render API for the Web, based on fully described design systems. Both serializable in JSON and usable using the host languages primitive data types.

We kept it compact (around 12 keywords) and high-level (the keywords are mostly UI concepts, related to the description format: components, styles, theme...).

Example:

```json
{
  "@component": "card",
  "@variant": "horizontal",
  "header": "Card title",
  "content": {
    "@element": "p",
    "@content": "Welcome!"
  }
}
```

## template.schema.json

### A templating language for components

Nothing fancy. We took Jinja, the industry standard, and did some light changes: removal of harmful filters and functions, identifications of slots filters and props filters, and a few additions.

Very easy to learn. Such a limited and focused language was chosen because powerful languages inhibit information reuse.

```jinja
<div {{ attributes|add_class("slider") }}>
{% for slide in slides %}
    <div class="slider__slide">
    {{ slide }}
    </div>
{% endfor %}
</div>
```

## validator.py

Just a simple tool, used by the Dilla team, no warranties are given.

### Setup

Build with docker:

```shell
make build
```

### Usage

```shell
docker login registry.gitlab.com
docker pull registry.gitlab.com/dilla-io/schemas:latest
```

Validate a payload (from STDIN):

```shell
echo '{"@element":"p","@content":"foo"}' | docker run -i registry.gitlab.com/dilla-io/schemas renderable
```

Validate definitions or templates in a design system:

```shell
docker run -v $YOUR_PATH:/data -t registry.gitlab.com/dilla-io/schemas definitions
docker run -v $YOUR_PATH:/data -t registry.gitlab.com/dilla-io/schemas templates
```

Validate all definitions and templates in a design system:

```shell
docker run -v $YOUR_PATH:/data -t registry.gitlab.com/dilla-io/schemas run
```

The validator will look for every design systems inside the mounted volume.

### Usage local

Example with a DS from [https://gitlab.com/dilla-io/ds](https://gitlab.com/dilla-io/ds)

```shell
make build
```

```shell
export DILLA_DS=bootstrap_4
curl -sL https://gitlab.com/dilla-io/ds/$DILLA_DS/-/archive/master/$DILLA_DS-master.tar.gz | tar -xz
docker run -t -v $(pwd)/$DILLA_DS-master:/data/ validator run
```

## Schemas packaging

The CI create a generic package of \*.schema.json to be served.

To download the package:

```shell
https://gitlab.com/api/v4/projects/46710238/packages/generic/schemas/1.0/schemas.1.0.tar.gz?private_token=_GITLAB_TOKEN_
```

```shell
curl --header "PRIVATE-TOKEN: _GITLAB_TOKEN_" \
  "https://gitlab.com/api/v4/projects/46710238/packages/generic/schemas/1.0/schemas.1.0.tar.gz" \
  --output "schemas.1.0.tar.gz"
```
