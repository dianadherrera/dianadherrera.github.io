.PHONY: build site pdf epub print dev clean

build: site pdf epub

site:
	zola build

pdf:
	cd scripts && uv run pdf.py

epub:
	cd scripts && uv run epub.py

print:
	cd scripts && uv run kdp.py

dev:
	zola serve --port 4000 --interface 0.0.0.0 --base-url /

clean:
	rm -rf public static/processed_images scripts/typst/data
