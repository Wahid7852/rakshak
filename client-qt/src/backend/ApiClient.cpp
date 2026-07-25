#include <rakshak/backend/ApiClient.h>
#include <rakshak/common/Settings.h>

#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonValue>
#include <QtNetwork/QHttpMultiPart>
#include <QtNetwork/QNetworkAccessManager>
#include <QtNetwork/QNetworkReply>
#include <QtNetwork/QNetworkRequest>

using namespace rakshak::backend;

namespace {
constexpr int kShortTimeoutMs = 10000;
constexpr int kScanTimeoutMs = 30000;
}

ApiClient::ApiClient(QObject* parent)
    : QObject(parent), m_net(new QNetworkAccessManager(this)) {
    reloadSettings();
}

ApiClient::~ApiClient() = default;

void ApiClient::reloadSettings() {
    const auto s = rakshak::common::Settings::instance().load();
    m_baseUrl = s.apiBaseUrl;
    while (m_baseUrl.endsWith('/')) m_baseUrl.chop(1);
    m_apiKey = s.apiKey;
}

QString ApiClient::url(const QString& path) const {
    return m_baseUrl + path;
}

void ApiClient::setAuthHeader(QNetworkRequest& request) const {
    request.setRawHeader("x-api-key", m_apiKey.toUtf8());
}

QString ApiClient::describeError(QNetworkReply* reply, const QByteArray& body) const {
    const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    switch (status) {
        case 401: return QStringLiteral("invalid API key");
        case 413: return QStringLiteral("file exceeds the backend's size limit");
        case 429: return QStringLiteral("rate limited by the backend, try again shortly");
        default: break;
    }
    const auto doc = QJsonDocument::fromJson(body);
    if (doc.isObject() && doc.object().contains("detail"))
        return doc.object().value("detail").toString();
    if (status > 0)
        return QStringLiteral("backend returned HTTP %1").arg(status);
    return reply->errorString();
}

void ApiClient::checkHealth() {
    QNetworkRequest req{QUrl(url("/health"))};
    req.setTransferTimeout(kShortTimeoutMs);
    auto* reply = m_net->get(req);
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit healthChecked(false, QString());
            return;
        }
        const auto obj = QJsonDocument::fromJson(body).object();
        emit healthChecked(true, obj.value("version").toString());
    });
}

void ApiClient::scanFile(const QString& localPath, const QString& context) {
    QFileInfo fi(localPath);
    auto* file = new QFile(localPath);
    if (!file->open(QIODevice::ReadOnly)) {
        delete file;
        emit fileScanError(context, localPath, QStringLiteral("couldn't open %1").arg(localPath));
        return;
    }

    auto* multiPart = new QHttpMultiPart(QHttpMultiPart::FormDataType);
    QHttpPart filePart;
    filePart.setHeader(QNetworkRequest::ContentDispositionHeader,
                        QVariant(QStringLiteral("form-data; name=\"file\"; filename=\"%1\"").arg(fi.fileName())));
    filePart.setHeader(QNetworkRequest::ContentTypeHeader, QVariant("application/octet-stream"));
    file->setParent(multiPart);
    filePart.setBodyDevice(file);
    multiPart->append(filePart);

    QNetworkRequest req{QUrl(url("/v1/scan/file"))};
    setAuthHeader(req);
    req.setTransferTimeout(kScanTimeoutMs);
    auto* reply = m_net->post(req, multiPart);
    multiPart->setParent(reply);

    connect(reply, &QNetworkReply::finished, this, [this, reply, localPath, context]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit fileScanError(context, localPath, describeError(reply, body));
            return;
        }
        const auto obj = QJsonDocument::fromJson(body).object();
        FileScanResult r;
        r.malicious = obj.value("malicious").toBool();
        r.score = obj.value("score").toDouble();
        r.confidence = obj.value("confidence").toDouble();
        r.model = obj.value("model").toString();
        r.reason = obj.value("reason").toString();
        r.sha256 = obj.value("sha256").toString();
        r.quarantined = obj.value("quarantined").toBool();
        r.quarantineId = obj.value("quarantine_id").toString();
        emit fileScanResult(context, localPath, r);
    });
}

void ApiClient::scanLogLine(const QString& line, const QString& context) {
    QJsonObject obj;
    obj["line"] = line;

    QNetworkRequest req{QUrl(url("/v1/scan/logline"))};
    setAuthHeader(req);
    req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    req.setTransferTimeout(kShortTimeoutMs);
    auto* reply = m_net->post(req, QJsonDocument(obj).toJson(QJsonDocument::Compact));

    connect(reply, &QNetworkReply::finished, this, [this, reply, line, context]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit logScanError(context, line, describeError(reply, body));
            return;
        }
        const auto obj = QJsonDocument::fromJson(body).object();
        LogScanResult r;
        r.suspicious = obj.value("suspicious").toBool();
        r.score = obj.value("score").toDouble();
        r.confidence = obj.value("confidence").toDouble();
        r.model = obj.value("model").toString();
        r.reason = obj.value("reason").toString();
        emit logScanResult(context, line, r);
    });
}

void ApiClient::listQuarantine() {
    QNetworkRequest req{QUrl(url("/v1/quarantine"))};
    setAuthHeader(req);
    req.setTransferTimeout(kShortTimeoutMs);
    auto* reply = m_net->get(req);

    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit quarantineListError(describeError(reply, body));
            return;
        }
        const auto arr = QJsonDocument::fromJson(body).object().value("entries").toArray();
        QVector<QuarantineEntryDto> entries;
        entries.reserve(arr.size());
        for (const auto& v : arr) {
            const auto o = v.toObject();
            QuarantineEntryDto e;
            e.quarantineId = o.value("quarantine_id").toString();
            e.originalPath = o.value("original_path").toString();
            e.quarantineFile = o.value("quarantine_file").toString();
            e.reason = o.value("reason").toString();
            e.sha256 = o.value("sha256").toString();
            e.timestamp = o.value("timestamp").toDouble();
            entries.push_back(e);
        }
        emit quarantineListResult(entries);
    });
}

void ApiClient::restoreQuarantine(const QString& quarantineId, const QString& destPath) {
    QJsonObject obj;
    obj["quarantine_id"] = quarantineId;
    obj["dest_path"] = destPath.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(destPath);

    QNetworkRequest req{QUrl(url("/v1/quarantine/restore"))};
    setAuthHeader(req);
    req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    req.setTransferTimeout(kShortTimeoutMs);
    auto* reply = m_net->post(req, QJsonDocument(obj).toJson(QJsonDocument::Compact));

    connect(reply, &QNetworkReply::finished, this, [this, reply, quarantineId]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit quarantineRestored(quarantineId, false, describeError(reply, body));
            return;
        }
        emit quarantineRestored(quarantineId, true, QString());
    });
}

void ApiClient::deleteQuarantine(const QString& quarantineId) {
    QNetworkRequest req{QUrl(url("/v1/quarantine/" + quarantineId))};
    setAuthHeader(req);
    req.setTransferTimeout(kShortTimeoutMs);
    auto* reply = m_net->deleteResource(req);

    connect(reply, &QNetworkReply::finished, this, [this, reply, quarantineId]() {
        reply->deleteLater();
        const auto body = reply->readAll();
        if (reply->error() != QNetworkReply::NoError) {
            emit quarantineDeleted(quarantineId, false, describeError(reply, body));
            return;
        }
        emit quarantineDeleted(quarantineId, true, QString());
    });
}
