# Auditoria da obtenção autenticada do APK

Data: 2026-10-12. O usuário autorizou explicitamente a sessão temporária,
com autenticação pessoal na janela Google, sem registro de credenciais e com
remoção local ao terminar a tentativa de download.

## Código e dependências examinados antes do login

O AppImage Linux 2.0.1 foi conferido por SHA-256 com a release oficial:
`bee9fa856ddc0b4dfa3e1c7c7bbfd6e91a893190e30b63c228f79f72a7c5e99c`.
Os módulos signin, linux_backend, mcbedrock_get, paths e apkset extraídos
correspondem byte a byte ao código examinado em tools/mcbedrock-get.

Dependências do bundle: gpsoauth 2.0.0, pywebview 6.2.1, requests 2.34.2,
urllib3 2.7.0, pycryptodomex 3.23.0 e certifi 2025.1.31.
O navegador usa GTK3/WebKit2 4.1 do host, disponíveis sem instalação global.

Também foram examinados login.cpp, common.cpp, api.cpp, checkin.cpp,
file_login_cache.cpp, http.cpp e gplaydl.cpp do Google-Play-API, revisão
`6ead91313122b1b732854c29edfb40dbad4abac6`.

O helper mostra accounts.google.com no WebKit. Após a autenticação pessoal,
get_cookies obtém o cookie oauth_token; gpsoauth.exchange_token solicita a
credencial de sessão. Não há leitura de campos de senha no código do helper.
A biblioteca oferece APIs de login com senha, mas este fluxo não as chama.
O backend escreve a configuração privada e solicita a versão exata ao Play.
Não encontrei mecanismo intencional de envio a terceiros na inspeção realizada.
Esta inspeção não equivale a uma prova formal de segurança de todas as dependências.

## Destinos de rede e transporte

- Autenticação visual: accounts.google.com e recursos da própria página Google.
- Troca de credenciais: HTTPS android.clients.google.com/auth.
- Check-in e catálogo autenticado: HTTPS android.clients.google.com/checkin
  e android.clients.google.com/fdfe/.
- APKs: endereços de entrega fornecidos pelo Google Play, normalmente CDNs
  Google. Não há origem de APK de terceiros configurada.
- O catálogo público de versionCode foi obtido de raw.githubusercontent.com
  antes do login. O controlador usa diretamente 971622101 e não atualiza esse
  catálogo enquanto a sessão existe.

O controlador exige TLS válido na troca gpsoauth, desativa redirecionamentos
nessa requisição e não herda proxies de ambiente. O patch local do cliente Play
exige HTTPS e validação de certificado/hostname; valida os destinos inicial e
efetivo antes de enviar cada requisição, incluindo redirecionamentos.
Permite somente famílias google.com, googleapis.com, googleusercontent.com,
gvt1.com e gvt2.com; rejeita nomes semelhantes, HTTP, credenciais na URL,
esquemas locais e portas diferentes de 443. Não relaxa TLS caso haja recusa.
Se Google retornar um destino não permitido, a transferência para e será auditada.

O callback usa a API documentada do libcurl:
[CURLOPT_PREREQFUNCTION](https://curl.se/libcurl/c/CURLOPT_PREREQFUNCTION.html),
executada antes da requisição, inclusive em redirecionamentos.
Fonte reproduzível: secure_google_transport.h e google-play-transport.patch.
O header deve ser copiado para lib/playapi/util/ do cliente antes da recompilação.

## Prevenção de vazamento local

acquire_owned_apks.py desativa core dumps e descarta stdin/stdout/stderr brutos
antes de importar os componentes de autenticação. Desativa logging Python.
Não persiste mensagens arbitrárias, exceções, respostas HTTP ou URLs assinadas.
Somente etapas fixas, percentuais, códigos de erro explicitamente permitidos
e nomes de arquivos podem aparecer no status estruturado.

Os dumps HTTP de http.cpp ficam sob #ifndef NDEBUG. A compilação Release tem
-DNDEBUG; os textos desses dumps também foram confirmados ausentes dos binários.

A sessão vive somente em recovery/play-acquisition/private-session, dono UID
do usuário e modo 0700. O processo usa umask 077, arquivos de credencial 0600
e contexto WebKit efêmero. Não consulta perfis de outros navegadores.

No bloco finally, backend.sign_out e signin.forget removem a sessão, inclusive
se login/download falhar. Arquivos temporários conhecidos e cache privado são
removidos; o status registra apenas se os arquivos sensíveis deixaram de existir.
A ausência é conferida pelos nomes/metadados, sem ler seu conteúdo.
Isso encerra a sessão local do helper; não modifica configurações nem revoga
sessões gerais da conta Google.

A conferência final identificou uma omissão na limpeza upstream: o cliente C++
também persiste device-arm64.conf.state, com estado de check-in e credenciais
de API. O arquivo permaneceu dentro da pasta privada, criado sob umask 077.
Seu conteúdo real não foi lido nem registrado. Foi eliminado, e a limpeza do
controlador foi ampliada para device-*.conf.state. O teste com sessão sintética
agora cobre explicitamente essa omissão. Cache privado residual também foi removido.

## Compatibilidade corrigida durante a autenticação

Uma tentativa retornou account_address_not_available. Google não forneceu o
endereço para identificação automática. O fallback do helper usava Tkinter,
que falha neste CachyOS porque libtk8.6.so está ausente; o ImportError era
convertido em string vazia, sem exibir a janela de confirmação.

O controlador agora usa um diálogo GTK somente para confirmar o e-mail nessa
situação. Não solicita senha e não grava o e-mail nos relatórios. Não altera
o launcher LOVE do TrimUI nem instala bibliotecas globalmente.

Para evitar perder uma sessão concluída quando a identificação automática
falha, o endereço completo é agora confirmado no GTK antes de abrir WebKit.
O campo exige endereço com @ e domínio; entrada inválida mantém a janela aberta.
A senha continua sendo digitada exclusivamente na página Google. Essa rota
alcançou google_login_completed e downloading_exact_build no teste desta sessão.

## Verificações de regressão

- Onze testes do instalador passaram, incluindo Source Stamp, publicação com
  backup, preservação de outro jogo, falha USB simulada antes de publicar a
  versão e sinalização imediata de parada aos trabalhadores paralelos.
- Dois testes de privacidade usam apenas sessões sintéticas. Tanto sucesso
  quanto erro descartam saída bruta, não registram o marcador secreto fictício
  e eliminam os arquivos de sessão.
- O teste C++ verificou famílias de URL permitidas, rejeições e callback
  de bloqueio antes da requisição. Não usou credenciais reais.
- Nenhum teste desta auditoria é prova de execução física do Minecraft.

Os estados e hashes locais sem credenciais ficam em
recovery/play-acquisition/authentication-audit.json e acquisition-status.json.
