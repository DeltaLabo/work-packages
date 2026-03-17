# work-packages

Genera fichas LaTeX/PDF para paquetes de trabajo cortos con entregables claros.

## Estructura

- `scripts/generate_work_packages.py`
- `data/work_packages.csv`
- `assets/images/`
- `output/tex/`
- `output/pdf/`

## Uso

```bash
python3 scripts/generate_work_packages.py
python3 scripts/generate_work_packages.py 012026
```

Luego podés abrir `output/tex/012026.tex` en VS Code y recompilar manualmente con LaTeX Workshop.
