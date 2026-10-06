#include <QCoreApplication>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTextStream>
#include <stdexcept>

namespace {
void require(bool condition, const char *message)
{
    if (!condition)
        throw std::runtime_error(message);
}

void requireStopped()
{
    for (const auto &pid : QDir(QStringLiteral("/proc")).entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        bool numeric = false;
        pid.toULongLong(&numeric);
        if (!numeric)
            continue;
        QFile name(QStringLiteral("/proc/") + pid + QStringLiteral("/comm"));
        if (name.open(QIODevice::ReadOnly))
            require(name.readAll().trimmed() != QByteArrayLiteral("xochitl"),
                    "A notebook editor is running. Refusing an inconsistent snapshot.");
    }
}

QJsonObject readJson(const QString &path)
{
    QFile file(path);
    require(file.open(QIODevice::ReadOnly) && file.size() < 8 * 1024 * 1024,
            "Cannot read bounded document metadata.");
    QJsonParseError error{};
    const auto json = QJsonDocument::fromJson(file.readAll(), &error);
    require(error.error == QJsonParseError::NoError && json.isObject(), "Invalid document metadata.");
    return json.object();
}

void copyEntry(const QString &source, const QString &destination, qint64 &bytes, int depth)
{
    require(depth < 12, "Unexpected notebook directory depth.");
    const QFileInfo info(source);
    require(!info.isSymLink(), "A notebook snapshot cannot follow symbolic links.");
    if (info.isDir()) {
        require(QDir().mkpath(destination), "Cannot create snapshot directory.");
        for (const auto &entry : QDir(source).entryList(QDir::AllEntries | QDir::NoDotAndDotDot | QDir::Hidden))
            copyEntry(QDir(source).filePath(entry), QDir(destination).filePath(entry), bytes, depth + 1);
    } else {
        require(info.isFile(), "Unexpected notebook file type.");
        bytes += info.size();
        require(bytes <= 512 * 1024 * 1024, "Notebook snapshot exceeds the 512 MiB safety limit.");
        require(QFile::copy(source, destination), "Cannot copy notebook snapshot.");
        require(QFile::setPermissions(destination, QFile::ReadOwner | QFile::WriteOwner),
                "Cannot protect notebook snapshot.");
    }
}
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        const auto args = app.arguments();
        require(args.size() == 3, "Expected notebook name and a new snapshot directory.");
        const QString destination = args[2];
        require(destination.startsWith(QStringLiteral("/home/root/remarkable-infinite-horizontal/backups/"))
                    && !destination.contains(QStringLiteral("..")) && !QFileInfo::exists(destination),
                "Snapshot destination must be new and inside the application backup directory.");
        requireStopped();
        const QDir documents(QStringLiteral("/home/root/.local/share/remarkable/xochitl"));
        QString id;
        const QRegularExpression uuid(QStringLiteral("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"));
        for (const auto &entry : documents.entryList({QStringLiteral("*.metadata")}, QDir::Files)) {
            const auto metadata = readJson(documents.filePath(entry));
            if ((args[1] != QStringLiteral("--all") && metadata.value(QStringLiteral("visibleName")).toString() != args[1])
                || metadata.value(QStringLiteral("deleted")).toBool())
                continue;
            if (metadata.value(QStringLiteral("type")).toString() != QStringLiteral("DocumentType"))
                continue;
            const QString candidate = entry.chopped(9);
            require(uuid.match(candidate).hasMatch(), "Unexpected notebook identifier.");
            const auto content = readJson(documents.filePath(candidate + QStringLiteral(".content")));
            if (content.value(QStringLiteral("fileType")).toString() != QStringLiteral("notebook"))
                continue;
            if (args[1] != QStringLiteral("--all"))
                require(id.isEmpty(), "Multiple notebooks have the requested name.");
            if (!id.isEmpty())
                id += QLatin1Char(',');
            id += candidate;
        }
        require(!id.isEmpty() || args[1] == QStringLiteral("--all"), "The named notebook was not found.");
        require(QDir().mkpath(destination), "Cannot create snapshot directory.");
        require(QFile::setPermissions(destination, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner),
                "Cannot protect snapshot directory.");
        qint64 bytes = 0;
        for (const auto &entry : documents.entryList(QDir::AllEntries | QDir::NoDotAndDotDot)) {
            for (const auto &notebook : id.split(QLatin1Char(','), Qt::SkipEmptyParts)) {
                if (entry == notebook || entry.startsWith(notebook + QStringLiteral(".")))
                    copyEntry(documents.filePath(entry), QDir(destination).filePath(entry), bytes, 0);
            }
        }
        QSaveFile manifest(QDir(destination).filePath(QStringLiteral("snapshot.json")));
        const QByteArray json = QJsonDocument(QJsonObject{
            {QStringLiteral("notebook"), id},
            {QStringLiteral("name"), args[1]},
            {QStringLiteral("bytes"), bytes},
            {QStringLiteral("software"), QStringLiteral("3.28.0.172")},
        }).toJson();
        require(manifest.open(QIODevice::WriteOnly) && manifest.write(json) == json.size()
                    && manifest.commit(), "Cannot finish snapshot manifest.");
        QTextStream(stdout) << id << '\n';
        return 0;
    } catch (const std::exception &error) {
        QTextStream(stderr) << "[infinite-horizontal] Snapshot failed: " << error.what() << '\n';
        return 1;
    }
}
