#include "secure_google_transport.h"
#include <cassert>
int main() {
    assert(owned_google_url("https://android.clients.google.com/auth"));
    assert(owned_google_url("https://r1.gvt1.com/package.apk"));
    assert(owned_google_url("https://play.googleapis.com/download"));
    for (const char* url : {"https://google.com.evil.example/", "https://evilgoogle.com/", "http://android.clients.google.com/auth", "https://owner@example.com/", "file:///etc/passwd", "https://android.clients.google.com:8443/auth"})
        assert(!owned_google_url(url));
    CURL* curl = curl_easy_init();
    curl_easy_setopt(curl, CURLOPT_URL, "https://example.com/");
    assert(google_prerequest(curl,nullptr,nullptr,443,0) == CURL_PREREQFUNC_ABORT);
    curl_easy_setopt(curl, CURLOPT_URL, "https://android.clients.google.com/");
    assert(google_prerequest(curl,nullptr,nullptr,443,0) == CURL_PREREQFUNC_OK);
    curl_easy_cleanup(curl);
}
