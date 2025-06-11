Add to ```~/.zshrc```:

```bash
lily() {
    docker run --rm \
      -v /Users/christophe.thiebaud/github.com/musicollator/bwv-zeug/lilypond/includes:/work/includes \
      -v "$(pwd):/work" \
      codello/lilypond:dev \
      -I /work/includes "$@"
}
```