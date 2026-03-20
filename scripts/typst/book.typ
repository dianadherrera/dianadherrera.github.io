// Poetry book PDF template
// Usage: typst compile book.typ --input data=book-data.json

#let data = json(sys.inputs.data)

#set page(
  paper: "a5",
  margin: (top: 2.5cm, bottom: 2cm, left: 2cm, right: 2cm),
  numbering: none,
  fill: rgb("#fffcf4"),
)

#set text(
  font: "Baskerville",
  size: 11pt,
  lang: if data.lang == "es" { "es" } else { "en" },
)

#set par(leading: 0.8em)

// --- Cover page ---
#page(margin: (top: 4cm, bottom: 2cm, left: 2cm, right: 2cm))[
  #align(center)[
    #if data.cover != none [
      #image(data.cover, width: 60%)
      #v(1.5cm)
    ]
    #text(size: 18pt, style: "italic")[#data.title]
    #v(0.5cm)
    #if data.subtitle != none and data.subtitle != "" [
      #text(size: 11pt, fill: luma(120))[#data.subtitle]
      #v(0.3cm)
    ]
    #text(size: 11pt, fill: luma(100))[#data.author]
  ]
]

// --- Entries ---
#for entry in data.entries [
  #if entry.type == "section" [
    #pagebreak(weak: true)
    #v(1fr)
    #align(center)[
      #text(size: 12pt, style: "italic", fill: luma(80))[
        #entry.body
      ]
    ]
    #v(1fr)
  ] else if entry.type == "picture" [
    #pagebreak(weak: true)
    #v(1fr)
    #align(center)[
      #if entry.image != none [
        #image(entry.image, width: 85%)
      ]
      #if entry.title != none and entry.title != "" [
        #v(0.5cm)
        #text(size: 9pt, style: "italic", fill: luma(100))[#entry.title]
      ]
      #if entry.caption != none and entry.caption != "" [
        #v(0.2cm)
        #text(size: 8pt, style: "italic", fill: luma(130))[#entry.caption]
      ]
    ]
    #v(1fr)
  ] else if entry.type == "poem" [
    #pagebreak(weak: true)
    // Poem image — full width, on its own before the text
    #if entry.at("image", default: none) != none [
      #v(1fr)
      #align(center)[
        #image(entry.image, width: 85%)
      ]
      #v(1fr)
      #pagebreak(weak: true)
    ]
    #v(1fr)
    #align(center)[
      #link(data.base_url + "/poems/" + data.slug + "/" + entry.slug + "/")[
        #text(size: 12pt, style: "italic", fill: luma(80))[#entry.title]
      ]
    ]
    #v(1cm)
    // Render stanzas — keep each stanza together
    #for stanza in entry.stanzas [
      #block(breakable: false)[
        #for segs in stanza [
          #for seg in segs [
            #if seg.at("b", default: false) [#strong[#seg.t]] else if seg.at("i", default: false) [#emph[#seg.t]] else [#seg.t]
          ] \
        ]
      ]
      #v(0.7em)
    ]
    #v(1fr)
  ]
]

// --- Support page ---
#pagebreak(weak: true)
#v(1fr)
#align(center)[
  #text(size: 12pt, style: "italic", fill: luma(80))[
    #if data.lang == "es" [Gracias por leer] else [Thank you for reading]
  ]
  #v(1cm)
  #text(size: 10pt, fill: luma(100))[
    #if data.lang == "es" [
      Este libro es gratuito. Si estas palabras tocaron algo en ti, \
      considera apoyar mi trabajo para que pueda seguir escribiendo.
    ] else [
      This book is free. If these words touched something in you, \
      consider supporting my work so I can keep writing.
    ]
  ]
  #v(0.8cm)
  #if data.donate != "" [
    #text(size: 10pt)[
      #link(data.donate)[#data.donate.replace("https://", "")]
    ]
  ]
  #v(0.4cm)
  #text(size: 9pt, fill: luma(130))[
    #if data.lang == "es" [
      Cada contribución, por pequeña que sea, me permite \
      dedicar más tiempo a la poesía.
    ] else [
      Every contribution, no matter how small, allows me \
      to dedicate more time to poetry.
    ]
  ]
]
#v(1fr)

// --- Illustration page ---
#pagebreak(weak: true)
#v(1fr)
#align(center)[
  #if data.at("illustration", default: none) != none [
    #image(data.illustration, width: 50%)
    #v(0.4cm)
    #text(size: 7pt, style: "italic", fill: luma(150))[
      J. Moninckx, _Moninckx Atlas_, vol. 4 (1682–1709)
    ]
  ]
]
#v(1fr)

// --- Copyright page ---
#pagebreak(weak: true)
#v(1fr)
#align(center)[
  #text(size: 9pt, fill: luma(130))[
    © #data.author \
    #v(0.2cm)
    #link("https://creativecommons.org/licenses/by-nc-nd/4.0/")[CC BY-NC-ND 4.0] \
    #v(0.2cm)
    #link(data.base_url)[#data.base_url.replace("https://", "")]
  ]
]
#v(1fr)
