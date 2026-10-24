# Báo cáo LaTeX

Build bằng WSL từ PowerShell:

```powershell
wsl.exe bash -lc "cd /mnt/c/Users/Poicitaco/Desktop/Hanoi_map_optimizer/report && latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex"
```

Đầu ra: `main.pdf`.
