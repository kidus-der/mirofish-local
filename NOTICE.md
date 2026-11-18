# Notice

MiroFish Local is a modified version of [MiroFish](https://github.com/666ghj/MiroFish), based on upstream commit `7657031`. The original authors keep their copyright and credit. Their commit history is preserved in this repository, and their documentation is in [docs/upstream](docs/upstream/).

## Modification notice

This version was modified in November 2026. The main changes are:

- Hosted model and Zep Cloud use were replaced with local Ollama, Graphiti, FalkorDB and reranking components.
- Network, request and browser protections were added for local-only use.
- Simulation setup, personas, graph memory and reports were changed to improve source grounding.
- Setup scripts, verification tools, tests, evaluation data and sanitized results were added.
- Upstream Docker packaging and repository automation were removed.

## License

This project is distributed under the GNU Affero General Public License, version 3. See [LICENSE](LICENSE). If you distribute this software, or let people use a modified version over a network, you must meet the AGPL source-sharing requirements.

Third-party packages and downloaded model files remain under their own licenses. Check those licenses before using them in your own work.
