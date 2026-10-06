#include "CanvasSettings.h"
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSaveFile>

CanvasSettings::CanvasSettings(QString path, QObject *parent)
    : QObject(parent), m_path(std::move(path))
{
    const QString directory = QFileInfo(m_path).absolutePath();
    if (!QDir().mkpath(directory)) {
        reportError(QStringLiteral("Cannot create infinite-canvas settings. The feature is disabled."));
        return;
    }
    if (!QFileInfo::exists(m_path))
        setEnabled(true);
    else
        reload();
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, [this] { reload(); });
    if (!m_watcher.addPath(directory))
        reportError(QStringLiteral("Cannot watch infinite-canvas settings changes."));
}

void CanvasSettings::reportError(const QString &error)
{
    if (error == m_error)
        return;
    m_error = error;
    if (!error.isEmpty())
        qWarning().noquote() << "[infinite-horizontal]" << error;
    emit errorChanged();
}

void CanvasSettings::failClosed(const QString &error)
{
    reportError(error);
    const bool stateChanged = m_enabled || !m_overrides.isEmpty();
    if (m_enabled) {
        m_enabled = false;
        emit enabledChanged();
    }
    m_overrides.clear();
    if (stateChanged) {
        ++m_revision;
        emit revisionChanged();
    }
}

void CanvasSettings::reload()
{
    QFile file(m_path);
    if (!file.open(QIODevice::ReadOnly) || file.size() > 4096) {
        failClosed(QStringLiteral("Cannot read infinite-canvas settings. The feature is disabled."));
        return;
    }
    QJsonParseError error{};
    const auto document = QJsonDocument::fromJson(file.readAll(), &error);
    const auto object = document.object();
    if (error.error != QJsonParseError::NoError || !document.isObject()
        || object.value(QStringLiteral("version")).toInt() != 1
        || !object.value(QStringLiteral("enabled")).isBool()) {
        failClosed(QStringLiteral("Infinite-canvas settings are invalid. The feature is disabled."));
        return;
    }
    const bool enabled = object.value(QStringLiteral("enabled")).toBool();
    QHash<QString, OverrideMode> overrides;
    const auto stored = object.value(QStringLiteral("overrides"));
    if (!stored.isUndefined() && !stored.isObject()) {
        failClosed(QStringLiteral("Infinite-canvas notebook overrides are invalid. The feature is disabled."));
        return;
    }
    const QJsonObject storedOverrides = stored.toObject();
    for (auto entry = storedOverrides.begin(); entry != storedOverrides.end(); ++entry) {
        const QString id = normalizedId(entry.key());
        const QString mode = entry.value().toString();
        if (id.isEmpty() || (mode != QStringLiteral("infinite") && mode != QStringLiteral("paged"))) {
            failClosed(QStringLiteral("Infinite-canvas notebook overrides are invalid. The feature is disabled."));
            return;
        }
        overrides.insert(id, mode == QStringLiteral("infinite") ? AlwaysInfinite : AlwaysPaged);
    }
    reportError({});
    const bool globalChanged = enabled != m_enabled;
    const bool overridesChanged = overrides != m_overrides;
    m_overrides = std::move(overrides);
    if (globalChanged) {
        m_enabled = enabled;
        emit enabledChanged();
    }
    if (globalChanged || overridesChanged) {
        ++m_revision;
        emit revisionChanged();
    }
}

bool CanvasSettings::save(bool enabled, const QHash<QString, OverrideMode> &overrides)
{
    QSaveFile file(m_path);
    QJsonObject stored;
    for (auto entry = overrides.begin(); entry != overrides.end(); ++entry)
        stored.insert(entry.key(), entry.value() == AlwaysInfinite
            ? QStringLiteral("infinite") : QStringLiteral("paged"));
    const QByteArray data = QJsonDocument(QJsonObject{
        {QStringLiteral("version"), 1}, {QStringLiteral("enabled"), enabled},
        {QStringLiteral("overrides"), stored},
    }).toJson(QJsonDocument::Compact);
    if (!file.open(QIODevice::WriteOnly)
        || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
        || file.write(data) != data.size() || !file.commit()) {
        reportError(QStringLiteral("Cannot save infinite-canvas settings. The previous setting is unchanged."));
        return false;
    }
    reportError({});
    return true;
}

void CanvasSettings::setEnabled(bool enabled)
{
    if (!save(enabled, m_overrides))
        return;
    if (enabled != m_enabled) {
        m_enabled = enabled;
        emit enabledChanged();
        ++m_revision;
        emit revisionChanged();
    }
}

QString CanvasSettings::normalizedId(const QString &documentId)
{
    QString id = documentId.trimmed().toLower();
    if (id.startsWith(QLatin1Char('{')) && id.endsWith(QLatin1Char('}')))
        id = id.mid(1, id.size() - 2);
    static const QRegularExpression uuid(
        QStringLiteral("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"));
    return uuid.match(id).hasMatch() ? id : QString();
}

bool CanvasSettings::effectiveEnabled(const QString &documentId) const
{
    const QString id = normalizedId(documentId);
    const auto mode = id.isEmpty() ? UseGlobal : m_overrides.value(id, UseGlobal);
    return mode == AlwaysInfinite || (mode == UseGlobal && m_enabled);
}

int CanvasSettings::overrideMode(const QString &documentId) const
{
    const QString id = normalizedId(documentId);
    return id.isEmpty() ? UseGlobal : m_overrides.value(id, UseGlobal);
}

void CanvasSettings::setOverrideMode(const QString &documentId, int mode)
{
    const QString id = normalizedId(documentId);
    if (id.isEmpty() || mode < UseGlobal || mode > AlwaysPaged) {
        reportError(QStringLiteral("Cannot save an override for an invalid notebook."));
        return;
    }
    QHash<QString, OverrideMode> updated = m_overrides;
    if (mode == UseGlobal)
        updated.remove(id);
    else
        updated.insert(id, static_cast<OverrideMode>(mode));
    if (updated == m_overrides)
        return;
    if (!save(m_enabled, updated))
        return;
    m_overrides = std::move(updated);
    ++m_revision;
    emit revisionChanged();
}
