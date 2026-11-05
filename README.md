# Headshot Sensitivity

Aplicativo Android independente para criar sugestões de sensibilidade para testar no Free Fire. A interface funciona localmente em WebView, sem login obrigatório e sem alterar arquivos ou configurações do jogo.

## O que inclui

- Gerador por etapas com modelo/marca do celular, perfil de resposta, tamanho sugerido do botão, DPI sugerida e seleção de várias armas numa configuração combinada.
- Catálogo com 84 entradas e 80 recortes transparentes, otimizados para uso local; ao tocar numa arma, o app anima a ação correspondente (disparo/recuo, golpe, arremesso, implantação ou triplo impacto).
- Tema tático de arsenal em grafite, amarelo e azul-ciano, com abertura cinematográfica de 7,35 segundos: M4A1, AWM e katana entram em perspectiva 3D, a retícula trava o alvo e um impacto final faz a transição para o app. Dois tiros e uma recarga são sincronizados com a cena; o som pode ser desligado no splash e a preferência fica salva localmente. Respeita a preferência do Android por movimento reduzido.
- Novo avatar Cartoon 3D no launcher quadrado, redondo e adaptativo; o master usado nos assets locais está otimizado em WebP.
- Diagnóstico do aparelho e perfil/histórico mantidos no dispositivo. As sugestões são pontos de partida; o app não aplica DPI nem altera o Free Fire.
- Notícias sincronizadas pela automação a partir da página oficial da Garena em português.

## Instalar e atualizar

Baixe `Headshot-Sensitivity.apk` na [Release mais recente](https://github.com/cristianalmeida34rt-del/headshot-sensitivity-novo/releases/latest). O APK mantém o mesmo `applicationId` e a chave estável usada nas versões anteriores para permitir atualização sobre a instalação existente. Não desinstale a versão anterior; aceite a confirmação de atualização do Android.

O workflow semanal consulta notícias oficiais às segundas-feiras, no horário de São Paulo, e publica nova Release quando há conteúdo novo. O workflow de build também compila e anexa o APK como artefato a cada push em `main`.

## Desenvolvimento

- Android nativo: Java, `minSdk 23`, `targetSdk 35`, Java 17/Android SDK 35.
- Interface local: HTML, CSS e JavaScript em `app/src/main/assets/`.
- Compilar localmente: `gradle assembleDebug`.
- Testes: `python3 -m unittest discover -s tests -v`.
- Recriar os recortes: `python3 scripts/build_weapon_art.py` (requer Pillow). Os WebP de origem e o mapeamento de procedência estão em `docs/weapon-art-source/` e `docs/weapon-art-sources.json`; os originais ficam fora do diretório empacotado no APK.

## Créditos

As artes de Free Fire pertencem aos seus respectivos titulares, incluindo a Garena. Este projeto é independente e não é afiliado, patrocinado ou endossado pela Garena. Consulte [créditos e procedência dos assets](docs/WEAPON_ASSET_CREDITS.md) antes de redistribuir os arquivos de arte.
