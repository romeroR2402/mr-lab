import io

from .rpc import Server


def main() -> None:
    # UTF-8 explícito sobre los descriptores 0/1 (Windows usa cp1252 por defecto).
    # closefd=False evita cerrar stdin/stdout del proceso al finalizar.
    stdin = io.TextIOWrapper(io.FileIO(0, "rb", closefd=False), encoding="utf-8")
    stdout = io.TextIOWrapper(io.FileIO(1, "wb", closefd=False), encoding="utf-8",
                              line_buffering=True, write_through=True)
    Server(stdin, stdout).serve()


if __name__ == "__main__":
    main()
