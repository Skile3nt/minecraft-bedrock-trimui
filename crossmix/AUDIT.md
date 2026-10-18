# Auditoria técnica — CrossMix / TrimUI Smart Pro

## Atualização 0.1.4 — nova falha física em 2026-10-12

Verificados os 3.789 hashes do manifesto 0.1.3: zero divergência. Última
tentativa 15:17:07Z: prepare_x11 executou, modo 1777, Weston escutou :0,
Xwayland iniciou e registrou "created wm, root 80". mcpelauncher-client pid
4998 carregou o linker Android, mas terminou com 1 antes de carregar Minecraft.
Primeiro diagnóstico: "No current EGL context or display"; primeira falha
fatal: SDL_EGL_CreateSurface, seguido de "EGLUT: failed to choose a config".
O SIGTERM e a asserção Weston observados depois ocorreram na limpeza da sessão.

Inspeção do Crusty fixado mostrou register_backend guardando somente o primeiro
segmento /proc/self/maps e call_from_backend comparando esse único intervalo.
Reprodução com Crusty ARM64 real, EGL/SDL sintéticos e QEMU:
SDL sem separate-code passa; com separate-code não é reconhecido e volta à
fachada EGL que exige contexto pré-existente. A ponte corrigida usa a identidade
do objeto carregado (dlinfo/dladdr), mantém o classificador original para outros
chamadores e preserva a fachada para o aplicativo. Os dois layouts passam.

Isso demonstra o defeito na integração e reproduz a mensagem física; o mapa de
memória real do firmware não está disponível em USB Storage. O novo registro
backend_route_recovered permitirá confirmar se essa era a causa no dispositivo.
Não foram especulativamente reduzidos GLES, depth/stencil ou qualidade gráfica.
FMOD host ausente foi um aviso não fatal, preservado para investigação posterior.

0.1.4 acrescenta resumo antes do teardown, histórico por tentativa e mensagem
específica de erro sem alterar o menu LOVE. O teste físico do jogo permanece
pendente; os registros de carga da biblioteca não comprovam gameplay.

## Atualização 0.1.3 — 2026-10-12

O GPU Test 0.1.2 passou no TrimUI físico: PowerVR Rogue GE8300, GLES 3.2,
GL_ERROR=0x0 e exit 0. Launcher, controles do menu e Diagnostics funcionam.
Minecraft 1.16.221.01 foi reconhecido, mas duas tentativas de 14:56 UTC falharam
antes de iniciar mcpelauncher-client: Weston não conseguiu fazer bind de
/tmp/.X11-unix/X0 porque o diretório não existia. Em seguida houve falha na
limpeza do compositor. session.sh detectou a queda e retornou 1 ao launcher.

A 0.1.3 cria o diretório temporário ausente com sticky bit, preservando
diretórios e sockets existentes, e distingue códigos de saída Weston/cliente
em crossmix-session.log. Falhas do probe nativo agora não ficam ocultas pelo
eval. Os binários, menu e controles são reutilizados sem reconstrução.

Todos os 11.512 arquivos da versão instalada foram conferidos: 11.511 hashes
iguais à instalação original; version.json mudou somente game_library_stat
(timestamps FAT atualizados pelo launcher). Todos os 3.786 arquivos originais
do manifesto 0.1.2 conferiram. Nenhum asset/biblioteca de Minecraft foi alterado.

O teste anterior no PC herdou /tmp/.X11-unix do ambiente KDE e não detectou
essa precondição. A nova regressão reproduz a ausência com sockets Unix reais,
confirma a falha do script anterior e valida o preparo corrigido, sem alterar
o IPC do PC. QEMU continua sendo evidência de integração, não de GPU/jogo real.
Relatório completo no AUDITORIA_TRIMUI.md da raiz do projeto.

As seções abaixo são o registro histórico da auditoria inicial.

Data: 2026-10-11. Estado: protótipo experimental, sem execução em hardware físico.
Base binária: Standard ARM64 v2.0.1. Checkout base: 01d367959ac35be2ece5082898e58845228110ab.
Referência CrossMix: tag v1.3.0, commit 611742be7c1965d8c5a0f6d1eac965c916371c71.

## Conclusão

É possível reutilizar os executáveis Standard; não foi necessário recompilar
mcpelauncher, Weston, Xwayland ou SDL. Foram compilados somente uma pequena ponte
de isolamento e um diagnóstico GLES2. A sessão Weston/Xwayland ARM64 passou em
QEMU usando os scripts de produção; o teste substitui o Minecraft por xdpyinfo.
A renderização real através de PowerVR, a interoperabilidade entre o driver do
firmware e a libc privada, controles, áudio e consumo de memória continuam pendentes.
Não há evidência de que o jogo já funcione no TrimUI, nem medição de FPS.

Há uma correção necessária na especificação inicial: Allwinner A133 possui
PowerVR GE8300, não Mali-G31. A SDL distribuída para o TrimUI chama seu backend
nativo de `mali`; esse nome não identifica a GPU instalada. A escolha do driver
é por caminhos reais de bibliotecas ARM64 e nós de dispositivo, sem Panfrost ou
suposições sobre GBM/DRM. [Brief oficial A133](https://www.allwinnertech.com/uploads/pdf/20210803142431e6.pdf).

## Arquitetura do projeto original

- `Minecraft Bedrock.sh`: encontra PortMaster, resolve firmware/plataforma/ABI,
  migra dados, carrega LOVE, abre o menu e entrega a versão selecionada ao runner.
- `lib/common.sh`, `platform.sh`, `abi.sh`, `performance.sh`, `audio.sh`:
  identidade, framebuffer/compositor, loader/ABI, orçamento de memória e áudio.
- `menu/*.lua`: menu LOVE com instalação de APK, versões, perfis, backups,
  configurações, diagnóstico e ações de manutenção.
- `setup_apk.sh`, `apkmeta.py`, `apk_groups.py`: validação e extração de APK/splits
  fornecidos pelo usuário; os dados Android ficam em versions e profiles.
- `run_bedrock.sh`: escolhe ARM64/armhf, calcula presets, prepara configurações,
  mapeamento evdev e áudio. O cliente EGLUT recebe a biblioteca Android do jogo.
- `weston_launch.sh` + Westonpack: infraestrutura de janelas X11/EGL; Crusty
  apresenta o conteúdo via SDL e EGL do fabricante. Não é um Android completo.
- `bin/mcpelauncher-client`, `bin/crusty-context-v1.so`: cliente ARM64 e entrega
  explícita do contexto SDL. `libs.aarch64`: dependências nativas selecionadas.
- `bin32`/`libs.armhf`: caminho alternativo não utilizado neste produto.
- `source_release`, `build/clients`: patches, commits e receitas de compilação;
  `tests`: fixtures e regressões; `compat`: política de versões e runtimes.
- RGDS, segunda tela e downloader H700 são produtos/recursos distintos. Não
  fazem parte do pacote CrossMix. O downloader opcional foi omitido.

## Release e ABI

A release estável mais recente consultada é [v2.0.1](https://github.com/DankMiimer/minecraft-bedrock-handheld-port/releases/tag/v2.0.1).
Ela recomenda 1.16.221.01; isso é evidência upstream em outros aparelhos,
não validação no TrimUI. Os binários ARM64 foram reutilizados da release.
Os poucos hooks de shell são aplicados sobre o checkout base e têm patch contra
v2.0.1 incluído no ZIP. O restante do payload Standard é preservado.

Inspeção ELF/version-info do cliente: AArch64, glibc até GLIBC_2.34,
libstdc++ até GLIBCXX_3.4.30 e CXXABI_1.3.13. As bibliotecas Android/Bionic do jogo
são carregadas pelo launcher e seus shims; não devem substituir bibliotecas glibc.
O firmware [TrimUI 1.0.4](https://github.com/trimui/firmware_smartpro/releases/tag/v1.0.4)
registra atualização para glibc 2.33. A versão real instalada deve aparecer no
probe; CrossMix sozinho não comprova qual firmware base está no aparelho.

A solução utiliza ld-linux/glibc 2.36 e libstdc++ GCC 12 privados, selecionados
por argumento `--library-path`, apenas nos executáveis ARM64 do port. Python,
Bash, LOVE e o frontend continuam com a libc do firmware. Uma variável
LD_LIBRARY_PATH inofensiva é mantida porque o Westonpack chama
strlen(getenv("LD_LIBRARY_PATH")) sem verificar NULL. O Xwayland recebe seu
runtime pelo próprio wrapper, sem contaminar o interpretador /bin/sh.

Dependências ausentes foram extraídas de pacotes oficiais ARM64 Debian
Bookworm; libjpeg-turbo8 veio do Ubuntu Jammy porque o módulo Xwayland exige
LIBJPEG_8.0, enquanto o runtime original oferece JPEG62. Nenhum pacote foi
instalado globalmente. Versões, URLs e SHA-256 estão em debian-lock.json.
EGL/GLES genéricos usados nos testes de `--help` são fixtures separadas;
não substituem o driver PowerVR no ZIP.

## Compatibilidade e decisões

| Área | Ambiente/risco | Adaptação e evidência |
| --- | --- | --- |
| CPU/ABI | Cortex-A53 / AArch64 | Cliente e runtimes reais carregam sob QEMU; somente ARM64 no ZIP |
| RAM | 1 GB, disponível menor | Presets upstream de orçamento; 30 FPS iniciais, cerca de 5 chunks; sem benchmark |
| GPU | PowerVR proprietário | Driver existente do firmware; não distribuído; GPU Test registra vendor/renderer/version |
| EGL/GLES | EGL fabricante e GLES2, extensões desconhecidas | SDL nativa + Crusty EGLUT + context bridge; compatibilidade real ainda requer dispositivo |
| DRM/GBM | Não presumir /dev/dri/card0 utilizável | Weston headless/noop; nenhuma criação artificial de card0; apresentação direta SDL |
| Weston | Wrapper original monta runtime, mata processos e usa caminhos compartilhados | Sessão própria com processos conhecidos e pasta temporária exclusiva |
| Xwayland | Binário sem opção -glamor; paths XKB relativos defeituosos | -shm, TCP desabilitado; cache e links XKB privados; handshake real ARM64 passou |
| Seat/input | Headless original usa libseat/libinput mesmo assim | libseat builtin com VTBOUND=0, sem serviço global nem troca de VT; input físico pendente |
| SDL2 | LOVE/Crusty dependem do backend `mali` | Descoberta da SDL do firmware e validação da lista de backends; teste GLES separado |
| libc | Firmware conhecido 2.33; cliente requer 2.34 | Loader e bibliotecas 2.36 privados; chamadas host não recebem novas bibliotecas |
| Áudio | ALSA esperado; mixer/dispositivo real desconhecidos | Resolvedor upstream preservado; libasound e dados privados; sem FMOD proprietário |
| Controles | SDL no menu, linux-gamepad/evdev no cliente | Banco PortMaster no menu; genmap upstream no jogo; sem gptokeyb concorrente |
| Menu | CrossMix chama scripts via /bin/sh | Entrada POSIX entra explicitamente em Bash; LOVE 11.5 já distribuído pelo CrossMix |
| Python | CrossMix distribui python3.11 | Wrapper local com PYTHONHOME do cartão; não cria links no sistema |
| Cartão | FAT32/exFAT sem links Unix | ZIP regular, aliases ELF desreferenciados; dados na mesma árvore evitando bind mounts |
| Atualizações | Atualizador genérico apagaria a adaptação | Bloqueado no produto CrossMix; dados devem ser preservados em atualização dedicada |

O [changelog Westonpack](https://github.com/binarycounter/Westonpack/wiki/Changelog)
registra correções específicas de SDL/GLES para TrimUI/PowerVR. O runtime exato é
fixado por checksum; o número no nome do squashfs não basta para identificar
seu conteúdo. A descoberta de bibliotecas não é um teste de contexto EGL.

## Isolamento e preservação

O código original permanece no histórico Git, branch crossmix-trimui. O ZIP
preserva entradas/scripts originais selecionados e o source ZIP upstream.
Os hooks só ativam a sessão própria com MCPE_CROSSMIX=1; as cinco suítes
relevantes de regressão upstream passam nos caminhos originais.

Crusty cria aliases fixos em /tmp e faz seleção de EGL conforme o endereço de
retorno do chamador. A ponte local substitui somente o helper exportado
load_lib_local, cuja assinatura e chamadas PLT foram verificadas no binário
fixado. Isso evita aliases de outras sessões e preserva o hook original de
dlopen; um wrapper geral de dlopen esconderia o chamador SDL. Não há leitura
de offsets de estruturas privadas. A ponte é específica desse runtime fixado.

Os únicos arquivos temporários são de sessão e os sockets X11 escolhidos pelo
próprio Weston. Não há mount, mknod, killall/pkill, instalação global, alteração
de governors, driver ou firmware. O launcher gerencia apenas seus filhos;
Weston/libseat pode abrir dispositivos de input disponíveis durante a sessão.
O wrapper destrutivo original westonwrap.sh é mantido no runtime como material
upstream, mas não é chamado pela adaptação.

## Testes executados e limites

`python3 -B crossmix/test.py` registra dez grupos em dist/test-results.json:
sintaxe, cinco suítes upstream (platform, ABI, audio, performance, early-exit),
perfil CrossMix sintético, rejeição de ELF x86, ponte de aliases, integridade
do ZIP/manifesto, carregamento ARM64 real, limpeza/exit status e handshake X11.
A fixture CrossMix é uma simulação explícita; não foi capturada de um TrimUI.

`crossmix/headless_test.py` usa os scripts de produção session/xwayland/xkbcomp,
com a fronteira de execução adaptada ao QEMU. Weston e Xwayland são binários
ARM64 reais; xdpyinfo substitui o jogo. Foram verificados conexão X11, resposta
de dimensões, retorno ao chamador e remoção da pasta temporária. O log completo
fica em dist/headless-results.json. Nenhum frame GPU foi renderizado nesse teste.

A suíte de áudio neutraliza a descoberta do PipeWire do computador host para
que a fixture ALSA seja independente do ambiente de desenvolvimento. Três
assertivas antigas de performance foram corrigidas: atribuições temporárias
antes de funções Bash não persistiam para a comparação seguinte. Não foi
alterada a política de performance original por causa dessas assertivas.

Não foram testados: criação de contexto PowerVR, Minecraft 1.16.221.01,
menu LOVE no painel, ambos os analógicos, vibração, botões, som, suspensão,
Wi-Fi/LAN, memória em mundo real ou versões anteriores. Não havia aparelho
nem APK fornecido legalmente no workspace.

## Próxima validação necessária

1. Extração do ZIP na raiz de um cartão CrossMix 1.3.0, mantendo dados existentes.
2. Abrir Minecraft Bedrock Diagnostics e Minecraft Bedrock GPU Test em Ports;
   recolher logs/crossmix-probe.json, crossmix-entry.log e crossmix-graphics.log.
   O teste GPU deve apresentar um quadro verde por cinco segundos e voltar ao menu.
3. Verificar menu LOVE, botões e retorno/relançamento antes de instalar o APK.
4. Fornecer APK oficial legalmente obtido 1.16.221.01 com arm64-v8a, ou conjunto
   completo de splits da mesma versão; instalar pelo menu, criar mundo novo,
   validar áudio/controles e registrar FPS/memória/temperatura sem alterar sysfs.
5. Somente após validar o launcher e a versão de referência, avaliar versões
   anteriores com bibliotecas arm64; não há promessa de suporte a versões
   antigas disponíveis apenas em armeabi-v7a.

## Distribuição

O ZIP contém zero APK, libminecraftpe.so ou conteúdo de usuário do Minecraft.
Não inclui driver PowerVR, FMOD proprietário ou firmware. Fontes dos componentes
novos e avisos disponíveis acompanham o pacote. Consulte THIRD_PARTY_NOTICES.md.
Há uma pendência real antes de distribuição pública: Westonpack não fornece no
material auditado todas as fontes modificadas e avisos de seus componentes;
a wiki ainda lista a publicação das fontes como trabalho futuro. Portanto este
artefato é um pacote experimental local, não uma release pública com auditoria
de redistribuição concluída. A pendência não foi ocultada nem substituída por
uma licença MIT que cobriria apenas o repositório Westonpack.

## Correção do bootstrap 0.1.1 (2026-10-11)

O usuário relatou retorno imediato ao menu ao abrir Diagnostics e um item chamado
CPU Test. O pacote 0.1.0 contém GPU Test, não CPU Test; esse nome e os arquivos
instalados precisam ser comparados com o cartão físico. Nesta investigação,
o dispositivo USB não estava presente no lsblk/findmnt; nenhum log real novo
foi acessado e nenhuma gravação de atualização no SD foi feita até esse ponto.

Constatações verificadas no código, sem atribuição prematura ao PowerVR/Weston:

- Diagnostics em 0.1.0 só escreve JSON e encerra: não tinha uma interface.
- O registro de entrada só começa após resolver caminhos, mkdir e wrappers;
  as falhas anteriores ficam sem evidência persistente.
- O atualizador oficial CrossMix v1.3.0 cria /bin/bash como link para BusyBox.
  O launcher usa arrays, [[ ]], source e outros recursos de GNU Bash. Foi
  incluído Bash 5.2 ARM64 e libtinfo6, extraídos de debs oficiais com hash fixado,
  sem tocar em /bin/bash. O loader privado afeta só o Bash, preservando o
  LD_LIBRARY_PATH de firmware para utilitários chamados por ele.
- O mesmo atualizador extrai python.zip para System; portanto PYTHONHOME=System
  não é, isoladamente, um erro. O wrapper agora verifica encodings/__init__.py
  e registra o interpretador/prefixo usados. A ausência da stdlib no cartão
  real continua sendo hipótese, não uma causa demonstrada.

Referência primária para Bash/Python:
https://github.com/cizia64/CrossMix-OS/blob/v1.3.0/System/updates/update_001.sh
O lançador de Ports usa /bin/sh, independentemente do shebang:
https://github.com/cizia64/CrossMix-OS/blob/v1.3.0/Emus/PORTS/launch.sh

As três entradas agora são autônomas, POSIX, com trap de saída e logs antes das
cargas de Python/Bash/SDL. Erros de descoberta não impedem o teste de Bash no
Diagnostics nem a tentativa independente do teste GPU. O resultado Diagnostics
usa, quando disponível, sdl2imgshow nativo por seis segundos, encerrando somente
seu próprio PID. O teste GPU registra etapas sem buffer e mostra verde por cinco
segundos; não invoca Weston. A disponibilidade dessa tela continua dependendo
de uma execução física: um processo vivo não comprova pixels exibidos.

A suíte ganha injeção de falhas no bootstrap (Python exit 47, stdlib parcial,
descoberta exit 23, processo gráfico exit 42, launcher exit 29), independência
das entradas e preservação do ambiente de bibliotecas para o Bash privado.
QEMU verifica arrays de GNU Bash ARM64. Os testes continuam sem comprovar
interface, GPU, áudio ou controles físicos. Novos testes físicos são necessários
antes de declarar corrigido o retorno ao menu observado pelo usuário.

## Logs físicos lidos na atualização USB (2026-10-11)

Cartão confirmado por USB TRIMUI ADB, serial 1c000c660500c8d251d,
UUID 1B16-2B5A, label CROSSMIXOS, Roms/Data/System/Apps/Emus/PORTS e
System/usr/trimui/crossmix-version.txt = 1.3.0. Versão instalada: 0.1.0.
O cartão contém exatamente CrossMix, Diagnostics e GPU Test; não há CPU Test.

crossmix-entry.log contém quatro relatórios completos. Python funcionou, SDL
carregou e anunciou backend mali, glibc = 2.33, fb0/disp/ion acessíveis. Todos
os relatórios apresentam como único problema PowerVR/Mali kernel device
unavailable. Essa condição termina entry.sh antes do dispatch Diagnostics/GPU;
não foi gerado crossmix-graphics.log. Assim foi identificado um bloqueio real
no probe, sem evidência de que Weston ou o driver tenham falhado. Os logs do
PortMaster consultados não contêm referência ao Minecraft/Bedrock.

A ausência/permissão dos nomes GPU adivinhados passa a warning. Permanecem
fatais arquitetura errada, bibliotecas ARM64 ausentes, SDL sem backend mali e
fb0 inacessível. O relatório declara gpu_validated=false. Um teste de regressão
reproduz a combinação observada usando bibliotecas simuladas, sem EGL no PC.
A correção é identificada como probe-node-warning-1 sobre a 0.1.1 experimental;
o ZIP fornecido não é sobrescrito. Manifesto, código e notas registram o delta.

No CachyOS, FAT foi montado pelo udisks com showexec: arquivos .sh e ELF sem
extensão aparecem 0644. Isso não preserva modos Unix no cartão e não demonstra
as permissões usadas pelo firmware; as execuções físicas prévias de Python/SDL
confirmam que o ambiente do aparelho difere. Não se altera o mount do CrossMix
nem se aplica chmod global. Entradas do menu são executadas via /bin/sh.


## Auditoria pós-teste físico e correção EGL 0.1.2

Estado inicial: Git limpo em b69417b; commits locais desde upstream 01d3679:
645abbc (adaptação inicial), 2458955 (Bash privado/instrumentação), b69417b
(nomes GPU ausentes passam a aviso). Nenhum commit posterior ou delta oculto
foi encontrado. O SD inteiro gerenciado corresponde ao manifesto da 0.1.1
com probe-node-warning-1: 3.785 hashes corretos, zero arquivo ausente/divergente.
Os três ZIPs antigos foram comparados; o ZIP probe-fix corresponde ao SD.

Os logs reais novos mostram Python 3.11.8 com stdlib, Bash 5.2.15, framebuffer
1280x720, glibc 2.33, Diagnostics exit 0, launcher exit 0 em duas execuções.
O usuário confirmou controles e interface do launcher. Firmware monta arquivos
como 0777, apesar de showexec/0644 no CachyOS: não há evidência de falha de
permissão no aparelho. Foram encontradas 432 ELF AArch64 e 12 ELF ARM32
herdadas e inativas (lib32/findlib32); o caminho CrossMix permanece ARM64.

Duas tentativas GPU falharam após SDL_Init e antes de criar contexto:
SDL_CreateWindow: Could not load EGL library. Também ocorreu setterm: erro
ao carregar libncursesw.so.6. O teste não chamou Weston/Xwayland; não existem
logs de uma sessão do jogo. Nomes/SQLite do frontend e scripts apontam para
Minecraft Bedrock GPU Test; não foi encontrado CPU Test nem roteamento CPU.
O aviso graphics-test é o estágio registrado, não uma opção CPU disfarçada.

A EGL selecionada (/mnt/SDCARD/System/lib/libEGL.so.1) foi inspecionada com
readelf: depende de libGL.so.1, RUNPATH=/opt/gl4es/lib, e importa
gl4es_GetProcAddress/proc_address/hardext. É fachada GL4ES; a precedência de
System/lib no probe era incompatível com a necessidade de EGL nativa. A causa
imediata é comprovada pelos logs; a resolução por nova seleção ainda depende
de execução física. O erro genérico SDL não fornece o dlerror interno antigo.

A 0.1.2 acrescenta descoberta nativa estrita só para GPU/jogo, rejeita GL4ES
e prefere firmware. Preserva a descoberta legada e o gate do launcher.
O teste carrega EGL explicitamente, verifica símbolos, configura GLES2 com
depth16, fixa os dois caminhos SDL e registra GL/extensões/erros. A sessão
do jogo recebe a mesma descoberta. LD_LIBRARY_PATH de filhos contém só
firmware/CrossMix por opção do teste/jogo; loader privado continua com
--library-path. O padrão /nonexistent permanece para outros chamadores e
continua satisfazendo o requisito não-NULL do módulo Westonpack.

Regressões encontradas: gate de nodes (corrigido b69417b), seleção EGL errada
(corrigida nesta versão), ambiente setterm privado (corrigido só teste/jogo).
Warnings C.UTF-8 indisponível e printf Broken pipe não impediram o menu; não
foram alterados locale global, frontend, LOVE, controles ou scripts de entrada.
Uma regressão automatizada compara esses arquivos byte a byte à 0.1.1.

A suíte passa a 12 grupos: anteriores + policy de logs físicos e mocks EGL.
Mocks exportam funções falsas sem gráficos; QEMU continua sem GPU física.
Não há APK nem versão instalada. O cliente Standard ARM64 já foi carregado
sob QEMU; seu jogo Android ainda depende do APK legal e do contexto PowerVR,
ponte Crusty, som e memória reais. Defaults permanecem 30 FPS/4–5 chunks,
sem afirmar desempenho. FMOD nativo é opcional segundo run_bedrock.sh; a
libfmod Android não substitui FMOD Linux. Não foi redistribuído FMOD.

Fonte primária da política de carga SDL2 (GL_DRIVER e EGL_DRIVER):
https://github.com/libsdl-org/SDL/blob/release-2.26.5/src/video/SDL_egl.c
Os relatórios e logs completos foram preservados em recovery/audit-* no
projeto e serão copiados ao backup da atualização no SD.

Reprodução adicional sob QEMU: usando a fachada real do cartão e as bibliotecas
privadas do pacote, dlopen falhou com undefined symbol: hardext. Resultado em
dist/egl-reproduction.json, sem SDL_CreateWindow nem contexto GPU no PC. Isso
reforça a incompatibilidade GL4ES/GLVND que estava escondida pela mensagem SDL.
O cartão também contém System/lib/libncursesw.so.6; sua ausência no ambiente
dos filhos, e não falta do arquivo no SD, explica o erro setterm.
# Retomada SDL/EGL — 0.1.5, 2026-10-14

Git inicial 44b0973, com somente sdl-trace.c não registrado (105 linhas,
salvo completo). Preservado e concluído. Novos observadores e teste A/B foram
compilados localmente; launcher LOVE, controles, cliente, Crusty, SDL/EGL/GLES
do firmware e GPU Test não foram reconstruídos/substituídos.

Logs físicos 0.1.4 preservados de 2026-10-12T15:40:22Z e leitura adicional
ADB da tentativa 15:59:19Z: Weston listening, Xwayland WM ready, cliente
retorna 1 antes de libminecraftpe.so. SDL_EGL_CreateSurface acusa
eglChooseConfig/EGL_SUCCESS; Crusty acusa contexto/display inexistentes.
SDL_GL_CreateContext/Invalid window é posterior, não a primeira falha.
Não há backend_route_recovered; o defeito QEMU de segmentos não demonstra
a causa do firmware. Nenhuma mudança de GLES/stencil/driver foi feita.

TrimUI apresentou ADB serial 1c000c660500c8d251d, aarch64/sun50iw10,
CrossMix 1.3.0 e /dev/mmcblk1p1 UUID 1B16-2B5A montado em /mnt/SDCARD.
Nenhum armazenamento SD era exposto ao PC nessa leitura. Bibliotecas reais
foram copiadas SOMENTE para recovery, fora do Git/ZIP:
SDL 2.26.5, libEGL.so dependente de libIMGegl.so, GLES dependente de
libIMGegl/libsrv_um/libglslcompiler/libusc. SDL possui apenas driver mali.
Xwayland é a janela intermediária do Crusty; não há suporte SDL X11/Wayland
no firmware observado. EGL nativo usa PowerVR; não confundir mali com GPU Mali.

Instrumentação: funções underscore do Crusty encaminhadas sem trocar seus
resultados; origem __SDL/__egl; SDL_GetError no retorno nulo; eglGetError
encaminhado sem mudar código, ou fotografia terminal claramente identificada.
Auditor glibc sem dependências libc registra referências/fornecedores dlsym
e relocations e retorna o endereço original. Não intercepta dlopen nem
funções de fachada que classificam o chamador por endereço de retorno.
Os PID files ficam somente no diretório privado temporário da sessão.

Novo SDL Test chama init_backend do Crusty real, com preloads/caminhos/sockets
do jogo, sem carregar Minecraft. Compara normal e carga explícita de EGL,
preservando os atributos reais GLES 3.2/stencil 8/flags 0xa2. Não promove B
a configuração de jogo. Cada variante e os logs anteriores são preservados.
O bloqueio rung/floor 3 da última instalação permanece separado do teste.

Durante os testes, o GCC recente tentou usar GLIBC_2.38 para conversão de PID.
Substituída por leitura e validação decimal simples; a ponte usa no máximo
GLIBC_2.34. O loader privado 2.36 executou os observadores sob QEMU.
Isso verifica compatibilidade do diagnóstico, não gráficos físicos.


## Controles e encerramento — ciclo 0.1.7, 2026-10-14

**Base auditada:** HEAD fc89f2c, 0.1.6-experimental, Git limpo antes deste ciclo.
Cartão USB /dev/sda1 em /run/media/skile/CROSSMIXOS, serial
1c000c660500c8d251d, label CROSSMIXOS, UUID 1B16-2B5A e CrossMix 1.3.0.
Roms, Data, System, Apps/PortMaster/PortMaster e Emus/PORTS confirmados.
Os 3.805 hashes do manifesto instalado coincidem, sem arquivos ausentes.
Logs/configurações originais foram copiados para recovery/controls-016-20261014T200405Z.

### Evidência física e causa da entrada

O usuário confirmou launcher/controles do launcher, Diagnostics e Minecraft
renderizando a tela Microsoft/Xbox na 0.1.6. Não confirmou jogo em mundo,
controles dentro do Minecraft, áudio ou encerramento normal.
O controller-test.txt físico já continha EV_KEY 304/305/307/308 e EV_ABS
0/1/3/4/16/17. Não identificava o rótulo físico correspondente a cada botão.

O processo real usa EGLUT/game-window/LinuxGamepad, libevdev e
libs.aarch64/libudev.so.1; não usa SDL_GameController para a entrada do jogo.
O launcher LOVE usa SDL2 do firmware. O mapeamento automático foi carregado
do perfil correto, mas uma linha SDL/gamecontrollerdb não cria dispositivos
que o backend recusou durante a enumeração.

Leitura ADB real, sem gravar no aparelho, confirmou /dev/input/event3,
TRIMUI Player1, BUS_USB 0003, VID 045e, PID 028e, versão 0114; capabilities
KEY=7cdb000000000000 0 0 0 0 e ABS=3003f. /run/udev e /run/udev/data não
existem. Os uevents do event3 e do input pai não têm ID_INPUT_JOYSTICK.
A biblioteca libudev carregada é uma implementação real dependente dessa base,
e o upstream só abre joysticks quando ID_INPUT_JOYSTICK retorna "1".
Isso identifica uma incompatibilidade concreta de descoberta. O efeito da
correção no recebimento pelo Minecraft ainda depende de novo teste físico.

Fontes fixadas utilizadas, também preservadas em recovery/input-source:
- https://github.com/MCMrARM/linux-gamepad/blob/68d75a74f80a93ec4ff7a96eea0909df28d45330/src/linux_joystick_manager.cpp
- https://github.com/minecraft-linux/game-window/blob/1777cab60232b20e47a36698d129faeb263ba357/src/joystick_manager_linux_gamepad.cpp
- source_release/linux-gamepad.patch e source_release/game-window.patch.

A ponte input-bridge.so é privada ao cliente real. Preserva propriedades
existentes, inclusive uma recusa explícita "0". Só fornece a propriedade
**ausente** após ioctl confirmar nome, quatro IDs, BTN_GAMEPAD e ABS_X/Y.
Não cria udev global, não altera permissões/dispositivos e não injeta eventos.
Os eventos continuam pelo mapeamento e callbacks nativos upstream. Registra
abertura e até 96 eventos de botões + 96 de eixos, preservando retorno/errno.

Minecraft Bedrock Input Test mostra prompts dos botões/analógicos com o
visualizador já existente do CrossMix. Registra rótulo físico, código e valor
em logs/crossmix-input-test.json. Não modifica mappings. Só após esse teste
podemos corrigir A/B, gatilhos ou adicionar emulação mouse/teclado com códigos
confirmados. Os gatilhos ABS_Z/RZ estão nas capacidades; o gerador upstream
não criou lefttrigger/righttrigger para esses eixos. A associação física
L2/R2 ainda não foi validada: nenhuma linha especulativa foi adicionada.
WESTON_NO_HEADLESS_INPUT, resolução, ponte EGL, drivers e launcher permanecem.

### Erro de saída real

A tentativa atual começou em 2026-10-14T19:55:13Z. Weston ouviu :0 às
16:55:14.164 local; Xwayland iniciou 16:55:14.978 e WM ficou pronto
16:55:15.312. Minecraft carregou a biblioteca 16:55:16, iniciou a atividade
Android, entrou em MinecraftGame::init e registrou métodos Xbox 16:55:22.
Xwayland encerrou com status 0 às 16:56:45.426; Weston recebeu TERM às
16:56:54.644. O cliente registrou "X connection to :0 broken". Não há
"Invoking stop activity callbacks" nesta execução. Não há evidência de erro
SDL/EGL, OOM ou encerramento normal solicitado pelo jogo.

O watcher herdava ERR e registrou saída 143 na linha 175 (sleep 1). O pai
registrou saída 1 na linha 12 (printf de log para stdout), seguido de
session_report_failed=1. O relatório JSON continuava sendo o teste limitado
anterior de 19:17, com exit 137: **não pertence à tentativa atual**.
A perda da conexão X e o sinal são observáveis; o emissor/origem da interrupção
não foi registrado, portanto não é possível afirmar quem encerrou Xwayland.
Há falhas demonstradas na supervisão/relato de saída, distintas de falha GPU.

Correções: sink de log em arquivo independente do tee; reporter stdout/stderr
redirecionados a arquivo (incluindo mensagens do wrapper Python); traps do
watcher removidos; JSON inicia com state=running e exit_code=null, sem reutilizar
resultado anterior; relatório distingue TERM/HUP, conexão X perdida, morte
prematura do Weston e watchdog de encerramento. O código real é preservado,
sem transformar encerramento forçado em sucesso. Cleanup mantém apenas PIDs
próprios e registra início/fim e uso de KILL. O grace de 15 segundos é mantido
até medições de um encerramento solicitado normalmente.

### Medições e limites de desempenho

startup-timing.log físico: LOVE iniciou em ~3s e primeiro frame do menu em
~4s, com precisão de um segundo. Bootstrap 19:55:00 até sessão 19:55:13 inclui
interação do usuário no launcher. Weston/Xwayland ficaram prontos em ~1s;
carregamento da biblioteca do Minecraft em ~2–3s após início da sessão;
registro Xbox em ~9s. Nenhum desses marcadores prova quando a tela de boas-
vindas apareceu. Não temos comparação de desempenho antes/depois.

crossmix-performance.jsonl mede uptime do bootstrap e da sessão, preparação,
Weston, execução do cliente, SDL_Init, janela/contexto, primeiro swap retornado,
marcadores biblioteca/JNI/atividade/Minecraft/Xbox e limpeza dos processos.
Primeiro swap não garante imagem visível; registro Xbox não garante popup.
Proc a cada 2s (até 30min) captura RSS/HWM, CPU ticks, bytes/rchar lidos,
MemAvailable/Dirty/SwapFree e contador OOM global. Logs só recebem campos
permitidos e marcadores fixos; nada de texto de teclado, senhas, tokens,
cookies, cmdline ou URLs de autenticação. O benchmark visual ainda exige
cronômetro/observação no aparelho; não foram alterados clocks, GPU, resolução,
distância de visão, saves, APK ou perfil de segurança (atualmente rung/floor 1).

### Validação e próxima etapa

Verificações do PC incluem interposição ELF versionada no host e QEMU ARM64,
identidade/capabilities/negação/fallback de gamepad, eventos e errno preservados,
limite do trace, captura guiada/parsers, privacidade da telemetria, stdout
fechado, TERM externo, códigos 0/42/143, relatório novo e cleanup. Regressões
SDL/Crusty testam a ponte de entrada carregada junto do observador gráfico.
A suíte completa e a instalação serão registradas após sua conclusão abaixo.

O USB expõe também ADB, mas /proc/mounts confirmou cartão desmontado no
aparelho enquanto montado no PC. Não executamos jogo/teste gráfico nesse
estado, não fizemos remontagem/ejeção nem alteramos o sistema. Alerta FAT de
volume não desmontado corretamente já existia ao montar; hashes são íntegros.
Nenhum reparo foi executado; novas falhas USB/I/O interrompem a instalação.

Após ejetar pelo PC e sair de USB Storage, executar **Input Test** seguindo
cada prompt, depois **CrossMix**: tentar A/B, direcional, sticks e Start;
dispensar Microsoft/Xbox somente pela opção oferecida pelo jogo, sem login
neste teste. Se entrar no menu principal, abrir mundo pequeno e medir tempo
até tela/interface e retorno pelo encerramento normal do jogo. Reconectar
USB para ler crossmix-input.log, crossmix-input-test.json, crossmix-performance.jsonl,
crossmix-session-report.json e logs session/client/weston/entry. Emulação não
comprova controles, desempenho ou encerramento no TrimUI.

Validação concluída neste ciclo: 20 grupos da suíte crossmix/test.py passaram
no PC/QEMU. Após delimitar os logs de cleanup, passaram novamente os 10 testes
de sessão, 11 testes de relatório e o handshake com Weston/Xwayland ARM64 reais
sob QEMU. Os testes de telemetria/guiamento verificam parsers e campos permitidos,
não a visibilidade física do Input Test. Evidência: dist/test-results.json e
recovery/controls-016-20261014T200405Z; a 0.1.7 ainda não teve execução física.
