# Desempenho — próximos passos (base c989f2f)

Evidência dos logs físicos arquivados: 381 amostras em ~763 s, polling de 2 s. Maior RSS reportado do cliente: 542.008 KiB; mínimo de MemAvailable: 262.628 KiB. Isso mostra margem de RAM limitada, mas não prova OOM nem pressão durante gameplay. `system_oom_kill` não trouxe valor.

CPU: há `cpu_ticks` acumulados do processo, sem HZ registrado, por núcleo, frequência ou recorte de gameplay; não permitem concluir gargalo. Chunks/leitura do microSD: sem latência, bytes ou tempos correlacionados a travadas. Renderização: nenhuma medição confiável de FPS/frame time. O SwapFree observado foi zero, mas não há amostra suficiente para atribuir impacto.

A sessão registrada usou ORIGINAL, 1280×720. `client_exec`→marcador `minecraft_init`: ~6,3 s; Xbox SDK: ~24,4 s (marcadores amostrados não provam primeira imagem/UI). O processo saiu com perda da conexão Xwayland; limpeza registrada levou ~1 s. Isso não explica a espera percebida antes do processo sair.

## Três experimentos prioritários

1. **Renderização: 1024×576 contra 1280×720**, mesmo mundo/percurso. São 36% menos pixels se a resolução interna do jogo realmente mudar. Impacto potencial alto se GPU-bound; risco médio, pois a superfície EGL não comprova resolução interna nem gameplay em escala reduzida.
2. **Texturas: orçamento 8 contra 4 por frame**, mesma cena com travessia de chunks. Impacto potencial médio em picos/stutter; risco médio de pop-in ou carregamento mais lento. Os logs não identificam o valor ativo nem medem uploads.
3. **Streaming de chunks/memória**, repetir percurso fixo e correlacionar frame time, RSS/MemAvailable e leitura/espera do cartão. Impacto potencial médio se as travadas coincidirem; risco baixo enquanto for só medição. Não há evidência para reduzir distância, mudar threads ou governor.

Faltam: frame time mediano/P95/P99 e FPS validado; resolução interna efetiva; CPU por núcleo/frequência durante gameplay; série temporal de RAM/pressão/OOM; latência e volume de I/O do microSD; tempo de carregamento dos mesmos chunks; temperatura/throttling; comparação A/B repetível. Usar o mesmo mundo, posição, percurso e duração, com perfil registrado. Não há FPS confirmado; ~25 continua sendo estimativa do usuário.
