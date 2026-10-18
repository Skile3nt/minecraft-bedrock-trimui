# 0.1.9 — checkpoint curto

Base funcional 0.1.8 / 5251c87, checkpoint 8943091. GPU/runtime/tema preservados.

Evidência física disponível: Minecraft joga/cria mundos; partículas visíveis;
L2/R2 não vinculam. FPS ~25 é estimativa do usuário, sem comparação medida.
SD confirmado USB TRIMUI ADB / serial 1c000c660500c8d251d / UUID 1B16-2B5A,
CrossMix 1.3.0. Última tentativa disponível: perfil ORIGINAL, 1280×720,
zero arquivos de partículas modificados. Isso demonstra inatividade do patch
nessa tentativa; não demonstra rejeição dos overrides pelo motor em outras.

Correção: padrão NO_PARTICLES/assets e entradas No Particles/Performance usando
o mecanismo local já existente. Original permanece rollback. As 127 definições
(121 identificadores) recebem alteração local com journal, backup/hash e
restauração ao sair. 126 têm orçamento de emissão zero; honey_drip mantém
emissão/colisão/áudio e billboard [0,0]. APK e biblioteca do Minecraft intactos.
Auditoria pós-escrita confirma hashes/identificadores no diretório redirecionado
pelo launcher; particle-audit.so observa no máximo 256 aberturas de JSON de
partículas desse diretório. Leitura não comprova aceitação semântica pelo motor.
Efeitos nativos ou emitidos por outro pack podem permanecer: nenhum patch binário.

Entrada: mapa carregado no jogo omitira lefttrigger/righttrigger. Firmware
TRIMUI Player1 anuncia ABS=3003f; logs reais mostram ABS_Z 0↔255. O log SDL do
PortMaster registra a2/a5 para o mesmo VID/PID/version. Novo arquivo de controls
com GUID+nome exatos acrescenta somente esses dois campos; o backend existente
transforma -1..1 em 0..1 e já transporta eixos ao Minecraft. Sem eventos sintéticos
ou nova ponte. Rastreamento dos eixos 2/5 tem orçamento separado dos sticks.
Input Test reduzido a L2/R2 registra rótulos físicos, pressão/liberação e limites.
Captura ADB de 45 s não recebeu eventos; ambos os rótulos e a vinculação no
Minecraft continuam pendentes de validação física. Não confundir com teste PC.

Testes: 8 casos de perfis/rollback; transformação e rollback byte a byte de todos
os assets licenciados em cópia privada no PC; observador ELF e ponte de entrada
em host/QEMU ARM64; parser/Gamepad upstream pinned 68d75a74 (pressionar/soltar
independentemente e ambos, stick preservado); 12 casos de sessão, bootstrap,
4 casos de telemetria segura e 11 relatórios. Sem benchmark novo ou ganho confirmado.

Próximo teste: ejetar normalmente após sync; Input Test (L2 depois R2), iniciar
No Particles, vincular gatilhos e testar pressão/liberação; quebrar terra/pedra/
madeira, observar fumaça/água. Logs em Data/ports/minecraftbedrock/logs:
crossmix-input-test.json, crossmix-input.log, crossmix-profile-018.json,
crossmix-particle-audit.log e crossmix-client.log. Se partículas persistirem,
correlacionar leituras e primeiro erro do conteúdo antes de tocar funções nativas.
Original restaura mudanças gerenciadas; backup USB permite rollback do código.
