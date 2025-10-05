{ stdenvNoCC, python3, fzf, }:
let name = "dashp";
in stdenvNoCC.mkDerivation {
  version = "2025-10-05";
  name = "${name}";
  nativeBuildInputs = [ python3 fzf ];
  dontUnpack = true;
  installPhase = ''
    install -Dm755 ${./dashp.py} $out/bin/${name}
  '';
}
