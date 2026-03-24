.PHONY: build site books pdf epub dev cms clean

build: site books

books: pdf epub

site:
	zola build

pdf:
	cd scripts && uv run pdf.py

epub:
	cd scripts && uv run epub.py

dev:
	uv run app/cms.py & zola serve --port 4000 --interface 0.0.0.0 --base-url /

cms:
	uv run app/cms.py

clean:
	rm -rf public static/processed_images scripts/typst/data
