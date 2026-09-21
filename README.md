# Sudoku, yhdeksällä värillä

Mikä tahansa tavallinen 9×9-sudoku ratkaistaan täsmällisenä graafivärityksenä. Vastauskantoja tai ulkoisia solvereita ei käytetä — vain graafin rajoitteet.

[Live-demo](https://semanassie.github.io/sudoku-graafivaritys/) (GitHub Pages)

## Idea

- 81 solua = 81 kärkeä.
- Särmä kahden solun välille, jos ne jakavat rivin, sarakkeen tai 3×3-laatikon → 810 särmää (jokaisella kärjellä 20 naapuria).
- Numerot 1–9 ovat yhdeksän väriä.
- Vihjeet ovat esivärjättyjä kärkiä eivätkä muutu.
- Graafin kelvollinen 9-väritys on täsmälleen kelvollinen sudoku.

## Algoritmi (DSATUR + takaisinotto)

1. Valitse värittämätön kärki, jonka naapureilla on eniten eri värejä.
2. Tasatilanteessa valitaan lähin edelliseen soluun, sitten pienin solun indeksi.
3. Kokeile sallittuja värejä nousevassa järjestyksessä (1–9) ja rekursioi.
4. Jos haara ei valmistu, peru. Kun koko graafi on värjätty, ratkaisu on valmis.
5. Haku voi jatkua toisen ratkaisun etsimiseen (yksikäsitteisyys).

Selainsovellus tallentaa sijoitukset, umpikujat ja takaisinotot, jotta haun voi toistaa askel kerrallaan.

## Selaindemo

Avaa `web/index.html` tai käynnistä paikallinen palvelin:

```sh
python3 app.py --open        # Python 3.10+
```

Syötä vihjeet (tai liitä 81 merkin merkkijono, tyhjä = `0` tai `.`) ja paina **Ratkaise**. Voit toistaa jäljen, näyttää ratkaisun tai ladata koko hakulokin JSON-tiedostona.

## Python-CLI

```sh
python3 solver.py --puzzle "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
python3 solver.py --puzzle-file puzzles/demo.txt --out qa/my-trace.json
python3 verify.py qa/my-trace.json
```

`--first-only` ohittaa yksikäsitteisyyshaun. `--timeout 120` pidentää hakua.

## Testit

```sh
python3 -m unittest -v
```

JavaScript- ja Python-toteutukset tuottavat saman ensimmäisen ratkaisun jäljen. `verify.py` ei tuo solveria: se rakentaa 27 sudoku-yksikköä, kaikki särmät ja toistaa jäljen itsenäisesti.

## Projektikartta

| Polku | Tarkoitus |
| --- | --- |
| `web/` | Win98-tyylinen selaindemo, JS-solveri ja jäljen toisto |
| `solver.py` | Python-graafivärityssolveri ja CLI |
| `verify.py` | Itsenäinen graafi-/jälki-/sudokutarkistus |
| `test_solver.py`, `test_browser_solver.py` | Käyttäytymistestit ja kielten välinen yhtenevyys |
| `puzzles/` | Demo- ja takaisinottoesimerkit |

Toteutus noudattaa [Chetas Luan MIT-lisensoitua](https://github.com/ChetasLua/sudoku-graph-coloring) graafiväritysmallia. Vain tavallinen 9×9 3×3-laatikoilla; diagonaali-, killer- ja epäsäännölliset variantit ovat rajauksen ulkopuolella.

MIT-lisenssi.
