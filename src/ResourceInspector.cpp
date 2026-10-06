#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QSet>
#include <QTimer>
#include <QDebug>

namespace {
quint64 resourceHash(const QByteArray &name)
{
    quint64 hash = 5381;
    for (const auto byte : name)
        hash = hash * 33 + static_cast<unsigned char>(byte);
    return hash;
}

void inspectResources()
{
    const QString output = qEnvironmentVariable("INFINITE_HORIZONTAL_INSPECTION");
    if (!output.startsWith(QStringLiteral("/home/root/remarkable-infinite-horizontal/inspection/"))
        || output.contains(QStringLiteral(".."))) {
        qCritical() << "[infinite-horizontal] Invalid inspection output directory.";
        QCoreApplication::exit(1);
        return;
    }
    if (!QDir().mkpath(output)) {
        qCritical() << "[infinite-horizontal] Cannot create inspection directory.";
        QCoreApplication::exit(1);
        return;
    }
    const QSet<QString> requested{
        QStringLiteral("/qml/device/view/documentview/DocumentView.qml"),
        QStringLiteral("/qml/device/view/documentview/DeviceSceneView.qml"),
        QStringLiteral("/qml/device/view/documentview/SceneViewGestures.qml"),
        QStringLiteral("/qml/device/view/settings/Display.qml"),
        QStringLiteral("/qt/qml/xofm/modules/library/ui/qml/EditDocument.qml"),
        QStringLiteral("/qt/qml/xofm/modules/library/ui/qml/EditDocumentWindow.qml"),
    };
    QJsonArray entries;
    QDirIterator resources(QStringLiteral(":/"), {QStringLiteral("*.qml"), QStringLiteral("*.js")},
                           QDir::Files, QDirIterator::Subdirectories);
    int saved = 0;
    while (resources.hasNext()) {
        const QString resource = resources.next();
        const QString path = resource.mid(1);
        const quint64 hash = resourceHash(path.toUtf8());
        QJsonObject entry{{QStringLiteral("path"), path},
                          {QStringLiteral("hash"), QString::number(hash)}};
        const bool relevant = requested.contains(path);
        if (relevant) {
            QFile input(resource);
            if (!input.open(QIODevice::ReadOnly) || input.size() > 2 * 1024 * 1024) {
                qCritical() << "[infinite-horizontal] Cannot read bounded editor resource.";
                QCoreApplication::exit(1);
                return;
            }
            const auto contents = input.readAll();
            const QString local = QString::number(hash) + QStringLiteral(".qml");
            if (qEnvironmentVariableIsSet("INFINITE_HORIZONTAL_CAPTURE")) {
                QSaveFile file(QDir(output).filePath(local));
                if (!file.open(QIODevice::WriteOnly) || file.write(contents) != contents.size()
                    || !file.commit()) {
                    qCritical() << "[infinite-horizontal] Cannot save editor resource.";
                    QCoreApplication::exit(1);
                    return;
                }
            }
            entry.insert(QStringLiteral("file"), local);
            entry.insert(QStringLiteral("sha256"),
                         QString::fromLatin1(QCryptographicHash::hash(contents, QCryptographicHash::Sha256).toHex()));
            ++saved;
        }
        entries.push_back(entry);
    }
    QSaveFile index(QDir(output).filePath(QStringLiteral("index.json")));
    const QByteArray json = QJsonDocument(entries).toJson();
    if (!index.open(QIODevice::WriteOnly) || index.write(json) != json.size() || !index.commit()) {
        qCritical() << "[infinite-horizontal] Cannot save resource index.";
        QCoreApplication::exit(1);
        return;
    }
    qInfo() << "[infinite-horizontal] Resources inspected:" << entries.size() << "selected:" << saved;
}

void initializeInspector()
{
    if (qEnvironmentVariableIsEmpty("INFINITE_HORIZONTAL_INSPECTION")
        || QCoreApplication::applicationFilePath() != QStringLiteral("/usr/bin/xochitl"))
        return;
    QTimer::singleShot(1000, QCoreApplication::instance(), inspectResources);
    QTimer::singleShot(5000, QCoreApplication::instance(), inspectResources);
}
}

Q_COREAPP_STARTUP_FUNCTION(initializeInspector)
