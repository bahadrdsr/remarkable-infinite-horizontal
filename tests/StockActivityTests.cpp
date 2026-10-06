#include "platform/StockActivity.h"
#include <QtTest>

using namespace infinitehorizontal;

class StockActivityTests : public QObject
{
    Q_OBJECT

private slots:
    void parseNamesWithSpacesAndParentheses()
    {
        const auto activity = parseThreadActivity(
            "123 (worker (display)) S 1 2 3 4 5 6 7 8 9 10 111 222 0 0 0 0 0 0 999");
        QVERIFY(activity);
        QCOMPARE(activity->ticks, quint64(333));
        QCOMPARE(activity->started, quint64(999));
        QCOMPARE(activity->state, 'S');
    }

    void rejectMalformedStat()
    {
        QVERIFY(!parseThreadActivity("123 missing parentheses"));
        QVERIFY(!parseThreadActivity("123 (xochitl) S 0 0"));
        QVERIFY(!parseThreadActivity("123 (xochitl) S 1 2 3 4 5 6 7 8 9 10 invalid 2 0 0 0 0 0 0 999"));
    }

    void requiresAnUnbrokenQuietWindow()
    {
        QuietWindow gate(600);
        StockActivity activity{{"1:100", "2:101"}, 50, false};
        QVERIFY(!gate.observe(activity, 0));
        QVERIFY(!gate.observe(activity, 500));
        activity.ticks++;
        QVERIFY(!gate.observe(activity, 600));
        QVERIFY(!gate.observe(activity, 1100));
        QVERIFY(gate.observe(activity, 1200));
    }

    void runningOrNewThreadsResetTheWindow()
    {
        QuietWindow gate(600);
        StockActivity activity{{"1:100"}, 50, false};
        QVERIFY(!gate.observe(activity, 0));
        activity.running = true;
        QVERIFY(!gate.observe(activity, 1000));
        activity.running = false;
        QVERIFY(!gate.observe(activity, 1100));
        QVERIFY(!gate.observe(activity, 1600));
        activity.identities.push_back("2:200");
        QVERIFY(!gate.observe(activity, 1700));
        QVERIFY(gate.observe(activity, 2300));
    }

    void missingThreadsAndBackwardsTimeCannotPass()
    {
        QuietWindow gate(600);
        StockActivity empty;
        QVERIFY(!gate.observe(empty, 0));
        QVERIFY(!gate.observe(empty, 2000));
        StockActivity activity{{"1:100"}, 50, false};
        QVERIFY(!gate.observe(activity, 3000));
        QVERIFY(!gate.observe(activity, 2500));
        QVERIFY(!gate.observe(activity, 2900));
    }
};

QTEST_GUILESS_MAIN(StockActivityTests)
#include "StockActivityTests.moc"
