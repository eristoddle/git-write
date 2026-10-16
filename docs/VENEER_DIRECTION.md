# Direction: GitWrite as a remote API for Veneer

*Planning note, 2026-10-16. High level only; details come later.*

- [Veneer](https://github.com/eristoddle/veneer), the desktop writing app, will have a GitWrite plugin.
- GitWrite runs as a **remote API**. The Veneer plugin is a thin client that calls it over the network (through Veneer's `api.net.fetch`).
- The current code was built quickly with early coding models and was barely tested. **Open decision:** keep and fix what's here, or collect the intent from it (writer-friendly terms, branching and cherry-picking, annotations, export) into a fresh plan and start over.
- Detailed planning hasn't started yet.
