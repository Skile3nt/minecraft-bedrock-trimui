# Medição de desempenho — preparação da próxima execução

Base revisada: `c989f2f`; código atual `0.1.9-experimental`.

- **Frames:** `sdl-trace.c` já conta 240 intervalos entre chamadas reais de apresentação, após confirmar o chamador Crusty `swap_buffers`. Registra `median_ms`, P95/P99, máximo, dimensões da superfície EGL/viewport e `submission_rate` (`240 / segundos`). Isso é cadência de frames submetidos pelo jogo, não confirmação de frames exibidos pelo painel nem FPS exclusivo de gameplay.
- **Ativação:** `session.sh` já define `MCPE_BENCH_FILE` para `logs/crossmix-frames.jsonl` em todas as sessões, inclusive `PERFORMANCE`; o hook está no preload existente. Nenhuma mudança é necessária. Batches são gravados a cada 240 intervalos, sem escrita por frame.
- **Dados disponíveis:** os arquivos preservados desta sessão não incluem `crossmix-frames.jsonl`. Portanto, a instrumentação existe, mas ainda não temos amostras físicas de frame time/submission rate para validar o resultado.
- **Sistema:** o coletor atual registra amostras a cada 2 s por até 30 min: RSS, memória disponível/pressão, CPU por núcleo, frequência, temperatura, estado térmico e I/O global do microSD. As amostras antigas arquivadas são da versão anterior e não contêm todos esses campos; falta uma sessão registrada com o coletor atual.
- **Mundos:** os logs mostram abertura de `minecraftWorlds/<id>/db`, mas não um marcador confiável de mundo pronto/primeiro frame jogável. A abertura do banco e a compactação não medem duração de carregamento. Não instrumentar `libminecraftpe.so` nesta etapa.
- **Conclusão:** registro de frame time e cadência de submissão já está habilitado no próximo perfil Performance. FPS de painel/gameplay e tempo de carregamento do mundo ainda não podem ser afirmados. Para comparar desempenho, coletar o JSONL da próxima sessão Performance e associá-lo ao mesmo mundo/percurso e janela de gameplay; tempo de mundo exige um marcador de conclusão confiável, ausente nos logs atuais.
