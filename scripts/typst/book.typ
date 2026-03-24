// Poetry book PDF template
// Usage: typst compile book.typ --input data=book-data.json

#let data = json(sys.inputs.data)
#let muted = rgb("#6e6358")
#let accent = rgb("#a0522d")
#let bg = rgb("#fffcf4")
#let border = rgb("#e8e2d6")

#set page(
  paper: "a5",
  margin: (top: 1.8cm, bottom: 2cm, left: 2cm, right: 2cm),
  numbering: none,
  fill: bg,
)

#set text(
  font: ("Iowan Old Style", "Palatino Linotype", "Palatino", "Georgia"),
  size: 11pt,
  lang: if data.lang == "es" { "es" } else { "en" },
)

#set par(leading: 0.8em)

// --- Cover page ---
#page(margin: (top: 1.8cm, bottom: 2cm, left: 2cm, right: 2cm))[
  #v(1fr)
  #align(center)[
    #text(size: 16pt, style: "italic")[#data.title]
  ]
  #v(0.8cm)
  #if data.cover != none [
    #align(center)[
      #image(data.cover, width: 80%)
    ]
  ]
  #v(0.8cm)
  #align(center)[
    #text(size: 10pt, fill: muted)[#data.author]
  ]
  #v(1fr)
]

// --- Entries ---
#for (i, entry) in data.entries.enumerate() [
  #if entry.type == "section" or entry.type == "interlude" [
    #pagebreak(weak: true)
    #v(1fr)
    #align(center)[
      #text(size: 12pt, style: "italic", fill: muted)[
        #entry.body
      ]
    ]
    #v(1fr)
  ] else if entry.type == "picture" [
    #pagebreak(weak: true)
    #align(center)[
      #if entry.title != none and entry.title != "" [
        #text(size: 14pt, style: "italic", fill: muted)[#entry.title]
      ]
      #if entry.caption != none and entry.caption != "" [
        #v(0.15cm)
        #text(size: 9pt, fill: muted, tracking: 0.08em)[#entry.caption]
      ]
      #v(0.25cm)
      #line(length: 0.8cm, stroke: 0.5pt + border)
    ]
    #v(1fr)
    #if entry.image != none [
      #align(center)[
        #image(entry.image, width: 100%)
      ]
    ]
    #v(1fr)
  ] else if entry.type == "poem" [
    #pagebreak(weak: true)
    #align(center)[
      #link(data.base_url + "/poems/" + data.slug + "/" + entry.slug + "/")[
        #text(size: 12pt, style: "italic", fill: accent)[#entry.title]
      ]
      #v(0.10cm)
      #line(length: 0.8cm, stroke: 0.5pt + border)
    ]
    // Epigraph
    #if entry.at("epigraph", default: none) != none [
      #v(-0.15cm)
      #align(center)[
        #text(size: 9pt, style: "italic", fill: muted)[
          #for seg in entry.epigraph [
            #if seg.at("url", default: none) != none [
              #link(seg.url)[#seg.t]
            ] else [
              #seg.t
            ]
          ]
        ]
      ]
      #v(0.5cm)
    ] else [
      #v(0.6cm)
    ]
    // Poem image
    #if entry.at("image", default: none) != none [
      #align(center)[
        #image(entry.image, width: 90%)
      ]
      #v(0.6cm)
    ]
    // Render stanzas
    #let single = entry.stanzas.len() == 1
    #for stanza in entry.stanzas [
      #block(breakable: single)[
        #for segs in stanza [
          #for seg in segs [
            #if seg.at("b", default: false) [#strong[#seg.t]] else if seg.at("i", default: false) [#emph[#seg.t]] else [#seg.t]
          ] \
        ]
      ]
      #v(0.65em)
    ]
    #v(1fr)
  ]
]

// --- Closing page: illustration + thanks + copyright ---
#pagebreak(weak: true)
#v(1fr)
#align(center)[
  #if data.at("illustration", default: none) != none [
    #image(data.illustration, width: 40%)
    #v(0.8cm)
  ]
  #text(size: 12pt, style: "italic", fill: muted)[
    #if data.lang == "es" [Gracias por leer] else [Thank you for reading]
  ]
  #v(0.5cm)
  #text(size: 9pt, fill: muted)[
    #if data.lang == "es" [
      Si estas palabras tocaron algo en ti, \
      tu apoyo me permite continuar en este camino.
    ] else [
      If these words touched something in you, \
      your support allows me to continue on this path.
    ]
  ]
  #v(0.3cm)
  #text(size: 9pt, fill: accent)[
    #link(data.base_url)[#data.base_url.replace("https://", "")]
  ]
  #v(0.8cm)
  #line(length: 0.8cm, stroke: 0.5pt + border)
  #v(0.5cm)
  #text(size: 8pt, fill: muted)[
    © #data.author · #link("https://creativecommons.org/licenses/by-nc-nd/4.0/")[CC BY-NC-ND 4.0]
  ]
]
#v(1fr)
