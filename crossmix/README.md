# Minecraft Bedrock — CrossMix-OS 1.3.0 / TrimUI Smart Pro

Adaptação experimental ARM64 0.1.6. Launcher, controles do menu, Diagnostics
e GPU Test EGL/GLES da 0.1.2 confirmados no TrimUI físico (PowerVR GE8300,
OpenGL ES 3.2, GL_ERROR=0x0). Minecraft completo ainda não foi validado.
Referência inicial: APK oficial 1.16.221.01, arm64-v8a, obtido legalmente.
Nenhum APK, biblioteca, asset ou mundo do Minecraft acompanha este pacote.
NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.

A 0.1.6 corrige uma causa comprovada pelos logs físicos da 0.1.5:
SDL solicitou EGL, mas recebeu funções de libCRU.so (fachada Crusty).
O pacote FAT contém aliases desreferenciados em arquivos ELF separados;
quando o cliente depende de libEGL.so.1, duas cópias Crusty são carregadas.
RTLD_NEXT na primeira encontra dlopen da segunda, que volta a interceptar
o carregamento nativo e entrega a fachada sem contexto. O classificador
SDL já retornava 1 corretamente: a correção de segmentos não bastava.

A sessão agora cria quatro symlinks em seu próprio diretório temporário
para o mesmo libcrusty.so preloaded. Assim, os aliases compartilham inode
e só uma instância Crusty é carregada. Não troca EGL/GLES/SDL, não reduz
atributos e não altera os arquivos de Crusty do cartão/firmware.
Crusty ARM64 real sob QEMU reproduziu falha com cópias e recuperação com
esses aliases, mantendo a fachada necessária ao aplicativo.

SDL Test auto/explicit passou no aparelho: GLES 3.2, depth24, stencil8,
GL_ERROR=0 e swap=1. Esse teste não inicializa o linker Android nem força
o cliente X11; Xwayland pode não ser acionado. Por isso, um sucesso no
teste isolado não prova que Minecraft iniciou. A tentativa real 0.1.5
identificou SDL_CreateWindow como falha e Weston/Xwayland vivos naquele ponto.

A 0.1.4 ainda falhou fisicamente em SDL_EGL_CreateSurface/eglChooseConfig,
com EGL_SUCCESS e "No current EGL context or display". O marcador
backend_route_recovered não apareceu: a correção de segmentos foi validada
sob QEMU, mas não foi demonstrada como causa dessa falha no firmware.

A 0.1.5 acrescenta diagnóstico, sem mudar os atributos gráficos do jogo.
sdl-trace.so registra SDL_Init, SDL_CreateWindow, SDL_GL_CreateContext,
SDL_GetError, versão/driver SDL, origens de funções e processos ativos.
egl-bind-audit.so registra o objeto que efetivamente forneceu cada símbolo
EGL ao SDL; devolve os mesmos endereços e usa somente o loader privado.
Os hashes das bibliotecas nativas ficam em crossmix-runtime-inventory.json.
O erro EGL após uma falha SDL é identificado como fotografia posterior:
SDL pode já ter consumido o erro original. Não confundir EGL_SUCCESS nesse
momento com sucesso da criação da superfície.

Nova entrada Ports: Minecraft Bedrock SDL Test. Executa duas sessões curtas,
sem carregar APK/jogo, com o mesmo Crusty/SDL/EGL/GLES/Weston do Minecraft.
A: inicialização normal; B: SDL_GL_LoadLibrary recebe EGL nativo explicitamente,
como no GPU Test. Ambas mantêm GLES 3.2/stencil 8 e os flags do Crusty.
O teste tenta apresentar azul durante três segundos quando contexto/superfície
existirem. Seu resultado fica em logs/crossmix-sdl-test.json, com códigos A/B e
diretório logs/sdl-test-*/auto e explicit. Uma variante bem-sucedida não habilita
automaticamente uma correção no jogo. O GPU Test verde existente foi preservado.

Primeiro execute SDL Test. Depois confira Diagnostics e o launcher/controles.
Se o modo de segurança bloquear Jogar após três falhas, preserve o estado:
SDL Test funciona independentemente desse bloqueio. A reativação do jogo exige
uma causa corrigida; não apague configurações, mundos ou launch_state.json.

A 0.1.3 superou a falha do diretório X11: Weston e Xwayland iniciaram no
TrimUI físico, e mcpelauncher-client foi executado. O primeiro erro novo foi
SDL/EGL sem configuração, com "No current EGL context or display" na ponte
Crusty, antes de carregar libminecraftpe.so.

A 0.1.4 corrige a identificação SDL/EGL na ponte local: Crusty guardava só o
primeiro segmento do mapa de memória e não reconhecia código em outro segmento,
redirecionando chamadas nativas para sua própria fachada. Esse defeito foi
reproduzido e corrigido com o Crusty ARM64 real sob QEMU e bibliotecas sintéticas.
A relação exata com o firmware será confirmada pelo novo registro
backend_route_recovered; não é comprovação de funcionamento físico do jogo.
Não foram alterados atributos GLES, menu, controles, APK ou mundos.

crossmix-session-report.json registra primeiro erro/falha fatal, processo,
status de Weston/Xwayland/cliente e marcadores de carga do jogo. As tentativas
são preservadas em logs/attempts/. crossmix-client.log inclui atributos SDL e
o resultado do roteamento. A tela de erro usa o diagnóstico da tentativa atual,
sem reaproveitar mensagem de uma execução antiga. O diagnóstico é gerado antes
da limpeza: SIGTERM/Broken pipe durante essa limpeza não são a causa inicial.

A 0.1.3 corrige uma falha anterior ao Minecraft: Weston tentava abrir o socket
/tmp/.X11-unix/X0, mas o diretório pai não existia no CrossMix. A sessão agora
prepara somente esse diretório temporário quando ausente, com modo 1777;
preserva diretórios, sockets e locks existentes. Não altera o firmware.
O código 1 anterior era retornado por session.sh após a queda do Weston,
antes de iniciar mcpelauncher-client. O modo de segurança não foi a causa.

Após instalar a atualização com backup, ejete pelo computador, desative USB
Storage e abra Minecraft Bedrock CrossMix > Jogar com 1.16.221.01 selecionado.
Se falhar, os logs em Data/ports/minecraftbedrock/logs são:
crossmix-session.log (etapas e códigos de cada processo), crossmix-weston.log
(compositor/Xwayland), crossmix-client.log (cliente/Android/jogo), launcher.log
e crossmix-entry.log (entrada completa). client_not_started indica que a
tentativa ainda não chegou ao cliente. Diagnostics e GPU Test permanecem
disponíveis; não é necessário repetir o GPU Test para diagnosticar este erro.
Esta correção precisa de novo teste físico do jogo.

Extraia o ZIP na raiz do cartão CrossMix. O menu Ports encontrará Minecraft
Bedrock CrossMix. O código fica em Data/ports/minecraftbedrock e os dados na mesma pasta, em
subdiretórios apk, versions, profiles e backups. Copie seu APK (ou todos os splits do mesmo
conjunto) para Data/ports/minecraftbedrock/apk após a primeira execução.
Use Install APK, depois Versions e Play. Não misture downloads de versões.

É necessário o runtime LOVE 11.5 que acompanha o PortMaster do CrossMix 1.3.0.
O pacote contém um loader glibc privado; não substitui bibliotecas do firmware.
Inclui GNU Bash privado: no CrossMix, /bin/bash pode apontar para BusyBox e
não oferece os recursos Bash usados pelo launcher. Python usa a instalação
completa extraída pelo atualizador do CrossMix para System, sem instalação global.
O driver PowerVR GE8300 e a SDL2 com backend denominado mali vêm do aparelho e não são redistribuídos.
A sessão própria usa Weston headless/noop + Xwayland para a janela EGLUT e
Crusty/SDL2/PowerVR para a apresentação real. Não usa renderização llvmpipe.
Nenhuma montagem, dispositivo DRM artificial, serviço seatd global, overclock ou
encerramento global de processos é feito pelo launcher CrossMix.

Os padrões iniciais são 30 FPS e 4–5 chunks, sem medição real de desempenho.
A resolução inicial segue o framebuffer detectado. Não forçamos um modo menor
antes de testar o scaler do aparelho. O menu permite ajustar FPS/distância.
A atualização genérica upstream é bloqueada para preservar a adaptação.
Logs ficam em Data/ports/minecraftbedrock/logs/crossmix-*. O primeiro teste
físico deve verificar o menu, as duas alavancas, todos os botões, áudio,
retorno ao menu e relançamento. Só depois devem ser avaliadas versões antigas.

Para reproduzir no computador: python3 crossmix/build.py --downloads ../downloads
O build verifica os downloads fixados e inclui os avisos de licença dos debs,
os patches/source_release upstream e o código desta adaptação.

Correção de hardware: o A133 usa PowerVR GE8300, não Mali-G31. O backend
SDL denominado mali é uma interface de framebuffer, não uma identificação
da GPU. Fonte primária: https://www.allwinnertech.com/uploads/pdf/20210803142431e6.pdf
O firmware TrimUI 1.0.4 informa glibc 2.33 nas notas oficiais:
https://github.com/trimui/firmware_smartpro/releases/tag/v1.0.4
O cliente exige 2.34; por isso usamos o loader privado 2.36.

O cartão pode usar FAT32/exFAT: dados e código ficam na mesma árvore para não
depender de symlinks ou bind mounts. Atualizações devem preservar apk, versions,
profiles, backups e config. Os aliases ELF do ZIP são arquivos regulares.
A entrada Minecraft Bedrock GPU Test testa um contexto GLES2 por cinco segundos
sem APK e registra GL_VENDOR/GL_RENDERER/GL_VERSION em crossmix-graphics.log.

Na versão 0.1.1, as três entradas registram o início antes de carregar Python,
Bash ou gráficos, incluindo etapas, stderr e código final de saída. Diagnostics
faz descoberta e verifica o Bash; tenta mostrar um resultado por seis segundos
com o visualizador nativo do CrossMix. Essa tela depende do SDL do firmware;
se não aparecer, o log continua sendo a referência. Diagnostics não executa
Weston nem cria contexto EGL. O teste GPU é independente de Weston e do APK.
O relatório principal é Data/ports/minecraftbedrock/logs/crossmix-entry.log;
crossmix-probe.json registra descoberta e crossmix-graphics.log registra EGL/GLES.
Se Data estiver ausente ou sem escrita, a entrada tenta registrar em
Roms/PORTS/Minecraft Bedrock bootstrap.log, depois /tmp/minecraft-bedrock-bootstrap.log.
Não há teste CPU separado neste pacote; se aparecer esse nome no menu,
confira o arquivo correspondente e o cache de nomes do frontend antes de atribuir
a falha ao teste GPU. Preserve os logs antigos para comparação.

A revisão local probe-node-warning-1 da 0.1.1 corrige um bloqueio confirmado
pelos logs físicos da 0.1.0: SDL mali carrega e fb0 é acessível, mas os nomes
de dispositivo GPU previstos pelo probe não são acessíveis. Essa ausência
agora é um aviso, e não encerra o launcher. Só o teste EGL/GLES pode validar
o contexto gráfico. HOTFIX.json e MANIFEST.json identificam a revisão; o ZIP
0.1.1 original permanece preservado no computador.

Antes de divulgação pública, consulte a pendência de fontes/avisos do Westonpack
em THIRD_PARTY_NOTICES.md. Este ZIP é um protótipo local. A auditoria completa
está em crossmix/AUDIT.md.

A 0.1.2 corrige a seleção EGL do teste: System/lib/libEGL.so.1 do cartão
auditado é uma fachada GL4ES (depende de libGL.so.1), que falhou ao carregar
no processo privado. O teste e a futura sessão do jogo usam --native-libraries:
preferem EGL do firmware e rejeitam essa fachada. O preflight do launcher
continua compatível; a descoberta nativa extra é informativa e não o bloqueia.
SDL_VIDEO_GL_DRIVER e SDL_VIDEO_EGL_DRIVER recebem caminhos explícitos.
A biblioteca glibc privada continua confinada aos argumentos do loader;
processos auxiliares de SDL recebem apenas diretórios do firmware/CrossMix.
O teste registra dlopen_EGL_error e símbolos ausentes, atributos GLES2,
GL_VENDOR/GL_RENDERER/GL_VERSION/GL_EXTENSIONS e GL_ERROR. Não usa Weston.
Se falhar, reconecte USB Storage para análise, preservando logs.
O APK 1.16.221.01 arm64-v8a continua necessário para instalar e jogar;
áudio do jogo, memória em mundo e a ponte gráfica Crusty não foram validados.


Versão 0.1.7 experimental: ponte privada para descobrir o gamepad nativo quando
falta ID_INPUT_JOYSTICK no CrossMix; correção de logs/relatórios durante saída;
telemetria de inicialização, RAM, CPU, I/O e cleanup. Minecraft renderizou a
interface Microsoft/Xbox na 0.1.6 física. Controles dentro do jogo e encerramento
normal ainda precisam de validação; não há benchmark de melhoria.

Novo menu Minecraft Bedrock Input Test: siga cada instrução de botão/stick.
O teste registra códigos físicos e não altera mappings. Em seguida abra
Minecraft Bedrock CrossMix, teste navegação A/B/direcional/sticks/Start e tente
dispensar a tela Microsoft pela opção disponível no jogo. Não é necessário
login para este teste. Registre os tempos até a tela visível e ao sair.

Logs em Data/ports/minecraftbedrock/logs: crossmix-input.log (descoberta/abertura/
eventos nativos limitados), crossmix-input-test.json (captura física guiada),
crossmix-performance.jsonl (timings e proc a cada 2s, até 30min),
crossmix-session-report.json e crossmix-{session,client,weston,entry}.log.
Relatório state=running significa tentativa sem relatório final; não é sucesso.
Não alteramos GPU, clocks, mundos/APKs, launcher visual ou seu controle.

0.1.8 Performance Pass A: entradas Original, No Particles e Performance (1024×576,
com gate EGL e fallback 1280×720).
Preferências/partículas são reversíveis, sem APK/assets no ZIP redistribuível.
Ver PERFORMANCE_0.1.8.md para teste físico, limites e rollback. Nenhum ganho
de FPS foi medido ainda; driver/tema branco permanecem.

0.1.9: padrão NO_PARTICLES / assets; a última execução 0.1.8 registrada era
ORIGINAL, sem overrides. Todas as 127 definições locais são verificadas por hash
antes de iniciar; o log crossmix-particle-audit.log observa leituras pelo processo.
Leitura/JSON válido não comprova aceitação pelo motor nem ausência física.
Mel preserva emissão/colisão/som com billboard de tamanho zero. Efeitos nativos
fora dos JSON podem permanecer. Original restaura assets e preferências.
Input Test agora solicita somente L2 e R2; modo completo com
MCPE_INPUT_TEST_MODE=full. Mapeamento de gatilhos a2/a5 mantém demais entradas,
fundamentado em capacidades evdev e registro SDL do próprio CrossMix;
vinculação e correspondência dos botões ainda precisam de teste físico.
Ver HOTFIX_0.1.9.md. Não há novo ganho de FPS confirmado.

0.2.1 mantém os lotes `crossmix-frames.jsonl` em `/tmp` durante a sessão e os
copia para `logs/` após o encerramento do cliente. A telemetria existente mede
intervalos entre apresentações verificadas do Crusty, não FPS de gameplay; isso
evita escrita periódica no microSD pela thread de apresentação sem mudar o jogo.
