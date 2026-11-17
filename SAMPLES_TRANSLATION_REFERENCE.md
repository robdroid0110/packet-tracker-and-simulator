# Sample labs and translation

The official sample/design-pattern guide describes concept builders, skill builders, design challenges and troubleshooting activities. Packet Tracker and Simulator includes four original examples based on those patterns. They use Packet Tracker and Simulator's own format and simulator; they are not copies of vendor activities.

Open **File → Open Samples…**, choose a sample and load it. This replaces the current workspace as **one undoable edit**: Undo restores the previous lab and Redo restores the sample. Save the lab normally if you want a separate persistent copy. The sample dialog stays available for its instructions and **Check current lab**. Checks run on a deep copy, so they do not change ARP, MAC tables, captures or the user's topology.

| Pattern | Example | Verification |
|---|---|---|
| Concept builder | Step through ARP/ICMP across a switch | Client-to-server connectivity; inspect packets and learned state separately |
| Skill builder | Obtain a router DHCP lease | Client reaches the router after configuration |
| Design challenge | Design two routed IPv4 subnets | Bidirectional reachability, distinct non-overlapping subnets and correct router gateways; multiple addressing plans work |
| Troubleshooting | Repair a disabled switch port | Client-to-server connectivity after repair |

Checks provide feedback; they are not an assessment tree or an activity timer. The activity wizard remains an unfinished section. vendor `.pkt` files have a partial topology importer; see [File import](FILE_IMPORT.md) for its limitations. vendor `.pka`, `.pkz`, `.ptl` and Qt language files are not imported or exported, and `.pkt` export is not supported.

## Agent API and CLI

- `GET /api/samples?language=eng` lists examples and instructions; use `spa` for Spanish. An unknown language returns 400.
- `POST /api/samples/action` with `{"action":"load","id":"skill-dhcp"}` loads the lab and autosaves. `{"action":"check","id":"skill-dhcp"}` returns JSON in `output`; `passed` and individual checks describe the result. Invalid IDs fail without changing lab state or saved bytes.
- `sample load skill-dhcp` and `sample check skill-dhcp` are equivalent Agent Shell commands. The capability registry exposes `samples.library`.
- `GET /api/samples/translation-template` returns the source template. `POST /api/samples/validate-translation` validates a candidate JSON object without writing it.

## Translating sample content

English, Spanish, Russian, Simplified Chinese, Hindi, Arabic, Portuguese, French, Bengali, Indonesian and Japanese sample titles/instructions are included. Arabic instructions use right-to-left layout. Translations should be reviewed by proficient speakers before relying on them for teaching. The language selector affects sample content only; the rest of Packet Tracker and Simulator and its help have not yet been translated. Sample language is a dialog choice rather than a saved-lab property.

To create another pack:

```sh
python3 tools/sample_translation.py template > new-language.json
# Edit id, language name, titles and instructions in UTF-8.
python3 tools/sample_translation.py validate new-language.json
# Add the reviewed pack as netsim/data/sample_languages/<id>.json.
```

Use a three-letter lowercase language ID and a matching filename. Every sample needs both fields. Placeholder tokens such as `%1`, `%n`, `[[NAME]]` and `{name}` must be preserved; translation validation rejects changed placeholders, invalid structure and oversized entries. Unicode text is displayed as text, not executable HTML. Packs are code-owned files loaded on request; the validation endpoint does not install files.

## Verification

Run `python3 -m unittest discover -s tests -q` and `python3 tools/verify_modes_devices.py --artifacts /tmp/packet-tracker-samples-evidence`. The isolated tests exercise all four examples, two-way undo/redo, real DHCP/repair/design outcomes, non-mutating checks, HTTP integration, Unicode and malformed translations. The Chromium run exercises the File menu, translated instructions, sample loading/checking and Undo, while verifying that the user's autosave bytes are unchanged.
