.PHONY: build site pdf epub dev cms clean

build: site pdf epub

site:
	zola build

pdf:
	cd scripts && uv run pdf.py

epub:
	cd scripts && uv run epub.py

dev:
	zola serve --port 4000 --interface 0.0.0.0 --base-url /

cms:
	uv run app/cms.py

clean:
	rm -rf public static/processed_images scripts/typst/data
