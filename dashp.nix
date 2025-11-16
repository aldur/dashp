{ stdenvNoCC, python3, fzf, }:
stdenvNoCC.mkDerivation {
  version = "2025-10-05";
  name = "dashp";
  nativeBuildInputs = [ python3 fzf ];
  dontUnpack = true;
  installPhase = ''
    install -Dm755 ${./dashp.py} $out/bin/dashp
    install -Dm755 ${./dashp-download.py} $out/bin/dashp-download
  '';
}
