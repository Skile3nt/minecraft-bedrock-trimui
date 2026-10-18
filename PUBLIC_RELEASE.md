# Minecraft Bedrock Launcher — preparação para distribuição

TrimUI Smart Pro original, CrossMix-OS 1.3.0, ARM64, PowerVR GE8300.
Versão de referência: Minecraft Android 1.16.221.01, versionCode 971622101.

## Conteúdo e instalação

A atualização Turquoise é cumulativa **sobre a adaptação CrossMix 0.1.9 ou
1.0.0-rc1 já instalada**. Não é uma instalação autônoma para cartão vazio.
Inclui o launcher, scripts da adaptação, fontes dos wrappers, bibliotecas abertas
já validadas, a capa aprovada e documentação. Não inclui APK, bibliotecas do
Minecraft, texturas clássicas licenciadas, mundos, contas ou sessões de login.

Os componentes ficam em `Data/ports/minecraftbedrock/`, a única entrada em
`Roms/PORTS/Minecraft Bedrock Launcher.sh` e a capa em
`Imgs/PORTS/Minecraft Bedrock Launcher.png`. Preserve as pastas `config`,
`profiles`, `versions` e `apk`; não substitua dados de outra pessoa.
Faça backup dos destinos existentes antes de atualizar; confira os SHA-256 do
manifesto e só retire o cartão após sincronizar e ejetar normalmente.

Cada usuário fornece sua cópia legítima ARM64. Use **Install APK**, após colocar
os APKs/splits correspondentes em `Data/ports/minecraftbedrock/apk/`.
O importador existente prepara o runtime; extração manual indiscriminada não
substitui esse procedimento. O download integrado permanece sujeito ao suporte
do dispositivo e não está habilitado no TrimUI. Não contorne autenticação/DRM.

## Interface

Destaques turquesa #00FFEF, fundo escuro. Game profile mantém Original,
No Particles e Performance. No Particles continua como padrão preservado.
Help, Support Bundle e Update Port foram retirados apenas do menu; ferramentas
internas e licenças continuam disponíveis. Credits usa a mesma navegação dos
demais menus: direcional para percorrer e B/voltar conforme o mapeamento ativo.

## Créditos e licenças

Port & Adaptation: Skile. Veja `CREDITS.md`, `AUTHORS.md`, `LICENSE`, `LEGAL.md`
e as licenças de dependências em `licenses/`. O trabalho original de DankMiimer,
minecraft-linux, MCMrARM, binarycounter e demais colaboradores permanece
creditado. O pacote clássico e os recursos do Minecraft não são redistribuídos.
Produto não oficial, sem associação/endosso de Mojang ou Microsoft.
Uma submissão pública ao PortMaster ainda requer revisão das licenças/fontes
correspondentes e validação física desta revisão. Este pacote não é uma
submissão ou aprovação do PortMaster.

## Limitações e validação

O caminho EGL pode recusar 1024×576 e usar o fallback 1280×720. A taxa de
apresentação não comprova FPS real. O erro histórico `recursive_mutex lock failed`
no encerramento não foi escondido nem corrigido especulativamente.
Não houve alteração de controles, gráficos, áudio, limites de FPS ou mundos.

Teste no aparelho: Play no mesmo perfil/mundo, anote quando o menu Minecraft
ficar visível; salve e saia normalmente e anote o retorno ao CrossMix. Repita
três vezes, separando partidas frias e quentes. Verifique também Credits,
controles/L2/R2, áudio, mundos e a persistência do salvamento.
Os eventos `play_selected`, `profile_prepare_begin/end`, `profile_restore_begin/end`
e `entry_return` complementam `logs/crossmix-performance.jsonl`.
A primeira apresentação e o registro Xbox não são marcadores de menu pronto.

## Reversão

O instalador conserva os destinos anteriores e os hashes em
`Data/ports/minecraftbedrock/backups/launcher-polish-<data>/install-plan.json`.
A reversão restaura exclusivamente esses arquivos, após conferir que os atuais
correspondem à atualização; arquivos novos são removidos somente por hash.
Mundos, configurações e dados do usuário nunca integram o overlay ou a reversão.
