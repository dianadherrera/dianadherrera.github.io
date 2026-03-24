// Generate a book cover image for EPUB
// Matches the PDF cover page layout
// Usage: typst compile cover.typ cover.png --root ROOT --input data=data.json

#let data = json(sys.inputs.data)
#let muted = rgb("#6e6358")
#let bg = rgb("#fffcf4")

#set page(
  width: 1400pt,
  height: 1870pt,
  margin: (top: 120pt, bottom: 120pt, left: 80pt, right: 80pt),
  fill: bg,
)

#set text(
  font: ("Iowan Old Style", "Palatino", "Georgia"),
)

#align(center)[
  #text(size: 96pt, style: "italic")[#data.title]
]
#v(1fr)
#if data.cover != none [
  #align(center)[
    #image(data.cover, width: 85%, height: 65%, fit: "contain")
  ]
]
#v(1fr)
#align(center)[
  #text(size: 72pt, fill: muted)[#data.author]
]
