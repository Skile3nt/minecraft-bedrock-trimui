# Launcher Turquoise — checkpoint

Base: `ab3f8d4`, branch `crossmix-trimui`, árvore limpa na entrada.
Checkpoint restaurável: tag `checkpoint/pre-turquoise-ab3f8d4`; ZIP rc1-r3 preservado.

- `7ee8656`: turquesa #00FFEF (sombras no mesmo matiz), fundo escuro; somente
  Help, Support Bundle e Update Port retirados do menu. Credits discreto,
  navegação reaproveitada; todos os demais itens e os três perfis preservados.
- Experimento `44ef2f6` (REVERTIDO após medição): sincronizações de diretório agrupadas para assets de partículas.
  Conteúdos e backups continuam com fsync individual; journal durável antes
  das trocas e preservado até que todos os diretórios sejam sincronizados.
  Falha de flush mantém o journal para recuperação. Nenhuma alteração em saves.
- Instrumentação existente ampliada com Play, início/fim da preparação e
  restauração do perfil, e retorno do script de entrada. Sem coletar dados de
  conta, texto ou eventos de controle.

## Linha de base física existente

Sessão registrada em 2026-10-18T15:56:14Z (não executada por esta sessão do Codex):
preparação da sessão → execução do cliente: 6,94 s; cliente → primeira
apresentação SDL retornada: 4,278 s; carregamento da biblioteca observado:
2,024 s. Nenhum desses marcadores equivale a menu pronto.
Solicitação de stop observada → cliente terminou: 1,068 s;
cliente terminou → limpeza da sessão terminou: 10,96 s.
Weston/métricas terminaram em 0,22 s; os 10,74 s seguintes incluem cópia das
métricas e restauração do perfil. O registro antigo não separava essas etapas.
Não atribuímos todo esse intervalo exclusivamente aos assets sem medir.
Não há dados suficientes para Play → menu Minecraft visível, nem retorno
visual ao CrossMix antes/depois. `entry_bootstrap` inclui tempo no launcher.

## Testes

Lua: callbacks reais de seleção, Credits/voltar, Game profile e Play com
camada gráfica não executada; sintaxe do menu e mensagens validada.
15 testes de sessão; bootstrap POSIX; 10 testes de perfis; recuperação do journal
incluindo interrupção parcial e falha de flush; simulação da instalação e
rollback preservando save e recusando sobrescrita de modificação posterior.
Failsafe aprovado. Controles e texturas não são alterados pelo overlay.
Nenhuma biblioteca nativa modificada ou recompilada nesta revisão.

Host, 120 assets sintéticos, mediana de três execuções:
preparação 113,13 → 111,91 ms; restauração 30,77 → 29,02 ms.
Diferenças pequenas, insuficientes para prometer aceleração física.
Operações de fsync em diretórios: preparação 135 → 16; restauração 122 → 3.
Fsync de arquivos preservados: 246 na preparação e 122 na restauração.
Cartão FAT via USB, host executando Python, 120 assets sintéticos, três repetições:
preparação 29,926 → 29,830 s; restauração 14,729 → 14,624 s.
Reduções de apenas ~0,3% / ~0,7%, insuficientes para sustentar ganho perceptível.
DECISÃO: reverter a otimização; manter a implementação funcional rc1.
Esses tempos incluem as operações instrumentadas de armazenamento e não são
tempos de abertura/encerramento do Minecraft no TrimUI. O teste completo levou
370,7 s, incluindo montagem de fixtures e limpeza, e não será repetido.
Os arquivos sintéticos foram removidos; nenhum asset ou mundo real foi usado.

## Entrega e limites

Overlay cumulativo sobre CrossMix 0.1.9/rc1, bibliotecas abertas reaproveitadas do
ZIP verificado; não é um pacote independente para cartão vazio. Documentação
em PUBLIC_RELEASE.md; créditos/licenças preservados. Sem APK/assets/saves.
Não há alegação de melhora de FPS, abertura total ou encerramento total.
Validação física pendente: aparência, navegação, Play, menu do Minecraft,
carregamento/salvamento, controles, áudio e saída normal. Comparar três vezes
no mesmo mundo/perfil e separar execuções frias/quentes. A otimização experimental já foi revertida; nenhuma mudança de desempenho
sem benefício demonstrado entra na atualização.

## Atualização mantida

Somente apresentação, documentação e instrumentação adicional. Bibliotecas,
controles, No Particles, texturas, gráficos, áudio, salvamento e algoritmos de
preparação/restauração rc1 permanecem idênticos à instalação funcional.
O teste de triggers C++ não foi reexecutado: exige fontes linux-gamepad externas
não localizadas nesta sessão; nenhum arquivo de entrada/controle foi alterado.
