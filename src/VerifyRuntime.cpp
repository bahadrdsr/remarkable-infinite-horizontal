#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QTextStream>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    const auto args = app.arguments();
    if (args.size() != 3)
        return 2;
    QFile manifest(args[1]), inspection(args[2]);
    if (!manifest.open(QIODevice::ReadOnly) || !inspection.open(QIODevice::ReadOnly))
        return 1;
    QJsonParseError manifestError{}, inspectionError{};
    const auto spec = QJsonDocument::fromJson(manifest.readAll(), &manifestError);
    const auto actual = QJsonDocument::fromJson(inspection.readAll(), &inspectionError);
    if (manifestError.error != QJsonParseError::NoError
        || inspectionError.error != QJsonParseError::NoError || !spec.isObject() || !actual.isArray())
        return 1;
    const auto files = spec.object().value(QStringLiteral("resources")).toObject();
    if (files.size() != 6)
        return 1;
    for (auto expected = files.begin(); expected != files.end(); ++expected) {
        int matches = 0;
        for (const auto &item : actual.array()) {
            const auto entry = item.toObject();
            if (entry.value(QStringLiteral("path")).toString() == expected.key()
                && entry.value(QStringLiteral("sha256")).toString() == expected.value().toString())
                ++matches;
        }
        if (matches != 1) {
            QTextStream(stderr) << "Native resource verification failed.\n";
            return 1;
        }
    }
    QTextStream(stdout) << "Native infinite-canvas resources verified.\n";
    return 0;
}
