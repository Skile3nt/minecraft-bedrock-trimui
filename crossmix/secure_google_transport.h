#pragma once
#include <curl/curl.h>
#include <algorithm>
#include <cctype>
#include <string>
#include <stdexcept>
static bool owned_google_url(const std::string& text) {
    CURLU* parsed = curl_url();
    if (!parsed) return false;
    char *scheme = nullptr, *host = nullptr, *user = nullptr, *port = nullptr;
    bool ok = curl_url_set(parsed, CURLUPART_URL, text.c_str(), 0) == CURLUE_OK;
    ok = ok && curl_url_get(parsed, CURLUPART_SCHEME, &scheme, 0) == CURLUE_OK;
    ok = ok && curl_url_get(parsed, CURLUPART_HOST, &host, 0) == CURLUE_OK;
    if (ok) {
        std::string name(host);
        std::transform(name.begin(), name.end(), name.begin(), [](unsigned char c){return std::tolower(c);});
        bool domain = false;
        for (const std::string suffix : {"google.com", "googleapis.com", "googleusercontent.com", "gvt1.com", "gvt2.com"}) {
            domain = domain || name == suffix ||
                (name.size() > suffix.size() && name.compare(name.size()-suffix.size(), suffix.size(), suffix) == 0 && name[name.size()-suffix.size()-1] == '.');
        }
        bool has_user = curl_url_get(parsed, CURLUPART_USER, &user, 0) == CURLUE_OK;
        bool has_port = curl_url_get(parsed, CURLUPART_PORT, &port, 0) == CURLUE_OK;
        ok = std::string(scheme) == "https" && domain && !has_user && (!has_port || std::string(port) == "443");
    }
    curl_free(scheme); curl_free(host); curl_free(user); curl_free(port); curl_url_cleanup(parsed);
    return ok;
}
static int google_prerequest(void* opaque, char*, char*, int, int) {
    char* current = nullptr;
    if (curl_easy_getinfo(static_cast<CURL*>(opaque), CURLINFO_EFFECTIVE_URL, &current) != CURLE_OK || !current)
        return CURL_PREREQFUNC_ABORT;
    return owned_google_url(current) ? CURL_PREREQFUNC_OK : CURL_PREREQFUNC_ABORT;
}
static void secure_google_transport(CURL* curl, const std::string& url) {
    if (!owned_google_url(url)) throw std::runtime_error("Unexpected Play transport destination; transfer stopped");
    curl_easy_setopt(curl, CURLOPT_PROTOCOLS_STR, "https");
    curl_easy_setopt(curl, CURLOPT_REDIR_PROTOCOLS_STR, "https");
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);
    curl_easy_setopt(curl, CURLOPT_PROXY, "");
    curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 5L);
    curl_easy_setopt(curl, CURLOPT_PREREQDATA, curl);
    curl_easy_setopt(curl, CURLOPT_PREREQFUNCTION, google_prerequest);
}
