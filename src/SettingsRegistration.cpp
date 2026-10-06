#include "CanvasSettings.h"
#include <QCoreApplication>
#include <QDir>
#include <QQmlEngine>
#include <QJSEngine>
#include <qqml.h>

namespace {
void registerSettings()
{
    if (QCoreApplication::applicationFilePath() != QStringLiteral("/usr/bin/xochitl"))
        return;
    qmlRegisterSingletonType<CanvasSettings>("InfiniteHorizontal", 1, 0, "CanvasSettings",
        [](QQmlEngine *, QJSEngine *) -> QObject * {
            return new CanvasSettings(
                QDir::homePath() + QStringLiteral("/.config/remarkable-infinite-horizontal/settings.json"));
        });
}
}

Q_COREAPP_STARTUP_FUNCTION(registerSettings)
