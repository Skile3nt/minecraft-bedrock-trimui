# Performance 0.1.8 — Pass A / checkpoint

Base: 0.1.7, código 4d75fc2, HEAD anterior 2c4d28a; Git limpo antes deste ciclo.
Usuário confirmou abertura, renderização 3D, menus, criação/exploração de mundos
com a maioria dos controles. L1/R1 funcionam; L2/R2 não. Não substituir runtime.

## Evidência atual

Cartão: TRIMUI ADB serial 1c000c660500c8d251d, CROSSMIXOS, UUID 1B16-2B5A,
CrossMix 1.3.0, /run/media/skile/CROSSMIXOS. Manifesto 0.1.7: 3.812 hashes iguais.
ADB readonly: aarch64/sun50iw10, sem mcpelauncher-client/Weston/Xwayland ativos;
SD desmontado no aparelho enquanto USB Storage o expõe ao PC. Não houve teste
GPU/jogo nesse estado. Não foi identificada separadamente a variante A133 Plus.
Snapshot privado: recovery/performance-018 (logs, opções e testes de assets).

Coleta real 0.1.7: 381 amostras, ~763s, pico VmHWM 528224 KiB, menor
MemAvailable 273368 KiB. Após uptime 180s, CPU média do cliente ~1,14 núcleos.
Isso inclui áreas/menus não identificados e não diagnostica CPU vs GPU.
read_bytes e contador OOM não estavam disponíveis; não interpretá-los como zero.
Sem FPS/frame times na 0.1.7. Saída 137 com conexão X perdida, sem fatal gráfico.
O options.txt ativo é profiles/1.16.221.01-971622101-arm64/mcpelauncher/games/
com.mojang/minecraftpe/options.txt. Arquivos antigos sob proc/<pid>/cmdline são
resíduos, não preferências alvo deste patch. Não alterar esses nem os mundos.

## Partículas

Assets reais: 127 arquivos JSONC, 121 identificadores únicos, format_version
1.10.0, taxas instant/steady/manual. Parser aceita comentários existentes
(guardian_water_move) e trailing commas, preservando strings Molang.
No Particles transforma 126 definições locais em 120 overrides únicos:
instant num_particles=0; steady spawn_rate/max_particles=0; manual max_particles=0.
Identificadores, referências, lifetime, textura e demais componentes preservados.
Inclui fumaça/fogueira/chama, quebra de blocos/itens, bolhas/água, poções,
explosões, partículas ambientais, portais e variantes 1.16. Mantém honey_drip
porque suas partículas disparam som: reduzir emissão ali também silenciaria o som.
Fogo, dano/explosões, água, mobs, poções e geração não foram alterados.

Primeira estratégia: resource pack gerado SOMENTE no perfil local licenciado,
manifest format 2, min_engine 1.16.0, mesma nomenclatura dos arquivos e mesmos IDs.
Ativação por global_resource_packs.json preserva packs pessoais. Nenhuma definição
Mojang é incluída no Git ou ZIP redistribuível. UI: verificar em Configurações >
Recursos Globais se TrimUI No Particles está ativo e observar efeitos conhecidos.
A precedência e aceitação pelo motor 1.16 ainda dependem desse teste físico.
Fallback explícito: entrada No Particles Assets, apenas se o pack falhar; modifica
os assets extraídos com cópias originais e hashes em backups/performance-018.
Não modifica APK nem libminecraftpe.so. Não há fallback automático especulativo.

Objetivo técnico é zerar os orçamentos de emissão, não transparência de texturas.
Ainda podem existir emissores vazios/efeitos nativos hardcoded; não há prova de
eliminação de todo custo de update/render nem de economia de CPU/GPU.
Documentação de apoio: https://github.com/Mojang/bedrock-samples/blob/main/documentation/Particles.html
A compatibilidade é baseada principalmente nos próprios assets 1.16, não só na
documentação atual. Não temos o validador binário Mojang isolado; JSON/estrutura
validados no PC não garantem a interpretação de zero pelo motor físico.

## Perfis e resolução

| Entrada em Ports | Partículas | Superfície solicitada | Preferências |
| --- | --- | --- | --- |
| Original / CrossMix padrão | originais | 1280×720 | equivalentes à 0.1.7 |
| No Particles | pack local | 1280×720 | somente bubble/particle distance existentes |
| Performance | pack local | 1024×576 com fallback nativo | Ultra Low opcional |
| No Particles Assets | transformação reversível | 1280×720 | fallback explícito |

mcpe_zoom_target(1280,720,1.25) upstream dá 1024×576, ambos alinhados a 16.
A sessão CrossMix retorna antes do fbset upstream. Reutilizamos CRUSTY_RESOLUTION,
comprovado no binário Crusty: dimensões são passadas à SDL_CreateWindow.
Weston, painel e sockets ficam 1280×720; cliente pede -ww1024/-wh576.
Antes de carregar Minecraft, probe curto no MESMO ambiente consulta a superfície
EGL nativa, não a fachada. Se não for 1024×576, volta a 1280×720 automaticamente.
Durante execução, batches registram EGL surface, SDL drawable quando disponível,
viewport e FBO. Só aceitar redução real quando superfície/viewport correspondem;
o preenchimento de todo painel, foco e legibilidade precisam de observação física.
Não há framebuffer/global fbset, troca de driver, FBO custom, shader scaler,
resolução dinâmica, governor, overclock ou afinidade. 768×432 foi adiado até
validar o scaler/benefício de 1024×576. Redução teórica: 36% dos pixels, não 36% FPS.

## Ultra Low e reversão

Só edita chaves que já existem: fancygraphics, fancyskies, toggleclouds,
smoothlighting, transparentleaves, bubble_particles, particleviewdistance,
texel_aa_2, viewbobbing, screen_animations, camera_shake. MSAA mantém 1 (um
sample; contexto físico anterior sem buffers multisample), não inventa valor 0.
Multithreaded renderer e async_texture_loads ficam iguais. FOV, gamma, tema,
controles, áudio, FPS/VSync e distância de 80 blocos/5 chunks preservados.
Streaming fica no 8 observado. config/performance-018.json pode solicitar 4/2
para outro A/B, mas nenhum orçamento menor foi escolhido sem medição.

As edições possuem backup/hash e journal durável ANTES de cada substituição.
No término, restaura preferências gerenciadas e remove somente nosso pack da
lista ativa, preservando alterações pessoais feitas no jogo. Se morto sem
cleanup, próximo perfil Original recupera o journal antes do jogo. Asset modificado
por terceiros causa recusa de sobrescrita. Packs locais gerados ficam inativos,
não publicados. Rollback lógico: escolher Original. Rollback de código: backups
USB da instalação 0.1.7; fazer automaticamente pelo PC numa sessão futura se preciso.

## Medição e teste físico curto

crossmix-performance.jsonl: CPU por núcleo, frequência reportada pelo driver,
RSS/HWM, cache/pressão/swap quando presentes, I/O global do SD, temperaturas.
A cada 2s; não escreve entradas de teclado, credenciais, cmdline ou URLs.
crossmix-frames.jsonl: batches de 240 intervalos, com mediana/P95/P99/máximo,
taxa de submissão e dimensões. Caller verificado como swap_buffers do Crusty,
que chama a SDL nativa uma vez por present neste binário. Não é scanout físico,
não separa sozinho menus de mundo, não agrupa percentis como se fossem brutos.
benchmark_summary.py filtra janela temporal; esta ferramenta será executada no
PC automaticamente quando os logs físicos forem disponibilizados.

Comparar Original → No Particles → Performance → Original. Mesmo mundo/área,
mesmo percurso, distância 5, mesma iluminação; aguardar 30s após entrar no mundo,
fazer percurso por 120s e anotar tempo desde Play até entrada no mundo. Salvar e
sair do mundo antes de encerrar o port. Registrar início da caminhada para
selecionar a janela correta dos logs, não incluir loading/menu no gameplay.
No Particles: quebrar bloco, observar fumaça/chama/água/poção/explosão visual sem
esperar remoção da mecânica. Performance: verificar tela inteira sem cortes,
menus legíveis, foco, áudio e controles. Se falhar, escolher Original/No Particles.
Reconectar USB para análise automática. Sem comparação física ainda: nenhum
ganho de FPS, memória, stutter ou load time foi declarado.

## L2/R2 e testes

Não existe crossmix-input-test.json desta execução; o trace limitado não contém
amostras de códigos 2/5. Capacidades anunciam esses eixos, mas não provam qual
gatilho físico corresponde a cada um. Mapeamento não foi alterado. Executar
Input Test para L2/R2; correção isolada posterior, sem arriscar controles atuais.

Testes específicos: 8 grupos de JSON/estrutura/backup/pack/preferências/recovery,
transformação local dos 127 arquivos reais (120 overrides) e rollback byte a byte;
500 swaps delegados sem alteração e batches/dimensões sob host + ARM64 QEMU;
12 testes de sessão incluindo gate aceito/rejeitado, fallback e restauração.
A suíte completa passou em 22 grupos no PC/QEMU; os novos campos de I/O
opcional foram verificados separadamente. ZIP/instalação seguem o mesmo controle
de hashes e backups do ciclo anterior. O registro final fica também na raiz do projeto.
Nenhum desses resultados comprova gameplay, scaler ou ganho físico da 0.1.8.
