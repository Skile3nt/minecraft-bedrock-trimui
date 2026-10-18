# Texturas clássicas — integração local sobre 0.1.9

Fonte escolhida: Tal Melamed, https://mcpedl.com/minecraft-classic-texture-pack/.
Download somente pelo link MediaFire dessa página, pasta 352dbug5b79pn,
arquivo 750nlkz3b6o48c7. Original: versão manifest 1.0.0, engine mínima 1.12.0;
SHA256 2f80a202416bf7abd55d61bb5ed45a0dc8e1b1abcb088dc10dee770b772545e3.
Original preservado em ~/Downloads/Classic Texture Pack.mcpack.

Variante pessoal: Classic-Texture-Pack-TrimUI-1.16.mcpack, versão 1.0.1;
SHA256 7f617e0b0ed7b5ec7470c5eb16b688b7043665347d43514d3fb583e7645d317f.
UUID header 81c6f272-6ee2-5b7e-9e7b-9926ee7f0cbc; módulo distinto, determinístico.
1053 imagens PNG/TGA, todas com caminhos existentes e dimensões exatamente
iguais aos assets 1.16 licenciados locais. Inclui terra, pedra, madeira, grama,
minérios, itens, água/lava e adaptações posteriores presentes na versão 1.16.
Água/lava mantêm strips de animação e fluxo com as dimensões nativas; nenhum
redimensionamento ou aumento de resolução. Atlas terrain altera somente a
entrada de quartzo do autor, reconhecida no atlas 1.16, com referências válidas.

Excluídos: UI, entidades/modelos/animações, sons, shaders, biomas, partículas,
imagens específicas de partículas/bolhas, arquivos não usados pela 1.16 e
imagens com dimensões incompatíveis. Assim o pack não restaura emissões nem
sobrepõe arquivos No Particles. UUIDs novos evitam colisão com o pack completo.
Prioridade: entradas globais existentes mantidas na mesma ordem; clássico ao
final. Nenhuma mudança no runtime, controles, desempenho, APK ou mundos.

Validação PC: CRC e SHA256 do original e da variante, decode de todas as imagens,
JSON/manifest, atlas/referências locais, colisões de nomes em FAT, UUIDs e teste
idempotente de ativação/desativação mantendo outros packs. Não comprova render
nem desempenho físico. Assets/artwork não incluídos no Git ou no ZIP público.

Rollback visual imediato: Minecraft > Configurações > Recursos Globais > Ativos,
desativar somente Classic Texture Pack - TrimUI 1.16. No Particles permanece.
Rollback completo pelo PC preparado em recovery/classic-textures/rollback.py,
com identidade USB, ausência do jogo, hashes, backup e sync; move o pack para
backup e restaura o global original quando inalterado, preservando outras
entradas adicionadas depois. Não executado no cartão: manter instalação visual.

Próximo teste físico: verificar pack nos Recursos Globais, abrir um mundo e
observar pedra/terra/grama/madeira/minérios, inventário e animações de água/lava;
confirmar ausência de texturas roxas, UI atual, controles e No Particles intactos.
Se não carregar automaticamente, ativar esse único pack em Recursos Globais.

Instalado e registrado nos Recursos Globais: 1056 arquivos verificados por hash;
137 arquivos protegidos conferidos sem mudança, incluindo definições No Particles,
configurações e controles. Sync concluído; armazenamento não ejetado.
Backup SD: Data/ports/minecraftbedrock/backups/classic-textures-20261014T222613Z.
O global_resource_packs.json original não existia; a ausência está registrada
em ROLLBACK.json. Nenhum pack anterior foi substituído. Rollback real do script
validado em duas fixtures isoladas no PC (global ausente / bytes anteriores),
com USB/ADB simulados; nenhum rollback executado no aparelho.
Carregamento visual e desempenho continuam pendentes do teste físico.
