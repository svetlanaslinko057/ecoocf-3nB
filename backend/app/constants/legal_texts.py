"""
legal_texts.py — canonical, full-length legal documents for the ECO.NOVA
public site (Terms of Use, Privacy Policy, Cookies Policy, Service Conditions).

Single source of truth:
  • `content.py` uses LEGAL_POLICIES as the default seed for `site_info.policies`;
  • `scripts/sync_legal_content_v2.py` pushes these texts into an existing DB.

The texts are written specifically for the hazardous-waste utilization domain
(B2B, Ukraine): waste codes per the national classifier, hazard classes 1–4,
licensing, ADR transport, contract-first flow, IBAN payments, client cabinet.
Admins can further edit everything in CRM → Контент сайту → «Політики та інфо».
"""

LEGAL_UPDATED_UK = "Дата останнього оновлення: 2 липня 2026 року."
LEGAL_UPDATED_EN = "Last updated: July 2, 2026."

# ═══════════════════════════════════════════════════════════════════════════
#  TERMS OF USE
# ═══════════════════════════════════════════════════════════════════════════

TERMS_UK = """
<h2>Умови використання</h2>
<p>Ці Умови використання (далі — «Умови») регулюють доступ і користування вебсайтом та онлайн-сервісами платформи ECO.NOVA (далі — «Платформа», «Сайт»), що належить ТОВ «ЕКО-НОВА» (далі — «Компанія», «ми»). Відкриваючи Сайт, реєструючи обліковий запис, надсилаючи заявку чи користуючись будь-яким сервісом Платформи, ви підтверджуєте, що ознайомилися з цими Умовами, розумієте їх та погоджуєтеся їх дотримуватися. Якщо ви не погоджуєтеся з Умовами — будь ласка, припиніть використання Сайту.</p>

<h3>1. Терміни та визначення</h3>
<ul>
<li><strong>Платформа</strong> — вебсайт, клієнтський кабінет, калькулятор вартості, каталог кодів відходів, блог та пов'язані онлайн-сервіси ECO.NOVA.</li>
<li><strong>Замовник</strong> — юридична особа або фізична особа-підприємець, що замовляє послуги з поводження з відходами.</li>
<li><strong>Відходи</strong> — речовини, матеріали і предмети, що утворилися у процесі діяльності Замовника та підлягають видаленню чи утилізації відповідно до законодавства України.</li>
<li><strong>Код відходу</strong> — класифікаційний код згідно з національним класифікатором відходів; кожна позиція каталогу на Сайті прив'язана до такого коду.</li>
<li><strong>Клас небезпеки</strong> — ступінь небезпечності відходів (класи 1–4), що визначає вимоги до пакування, транспортування та методу утилізації.</li>
<li><strong>Послуги</strong> — приймання, збирання, перевезення (у т.ч. за вимогами ADR), зберігання, оброблення, перероблення, знешкодження та утилізація відходів, а також документальний супровід цих операцій.</li>
<li><strong>Договір</strong> — окремий договір про надання Послуг, що укладається між Компанією та Замовником (онлайн-підписання або паперова форма).</li>
<li><strong>Клієнтський кабінет</strong> — захищений розділ Платформи, де Замовник керує заявками, договорами, рахунками та документами.</li>
</ul>

<h3>2. Статус Платформи та характер інформації</h3>
<p>Сайт надає інформацію про послуги Компанії, каталог кодів відходів із матрицею приймання, орієнтовний калькулятор вартості, форми заявок та блог із матеріалами про поводження з відходами. Уся інформація на Сайті має довідковий характер і <strong>не є публічною офертою</strong> у розумінні ст. 641 Цивільного кодексу України, якщо прямо не зазначено інше. Конкретні умови надання Послуг — обсяг, ціна, строки, місце — визначаються виключно Договором.</p>

<h3>3. Ліцензії та дозвільна документація</h3>
<p>Компанія провадить господарську діяльність з поводження з небезпечними відходами на підставі чинних ліцензій і дозволів, виданих уповноваженими органами України, та відповідно до вимог Закону України «Про управління відходами» і пов'язаних нормативно-правових актів. Перелік кодів відходів, які Компанія має право приймати, відображено у матриці приймання на Сайті. Компанія має право відмовити у прийманні відходів, що не входять до її дозвільної документації.</p>

<h3>4. Обліковий запис та клієнтський кабінет</h3>
<ul>
<li>Реєстрація у клієнтському кабінеті доступна суб'єктам господарювання (B2B). Під час реєстрації ви зобов'язані надати достовірні дані про компанію (назва, код ЄДРПОУ, контактна особа, телефон, email).</li>
<li>Ви несете відповідальність за збереження конфіденційності облікових даних та за всі дії, вчинені з вашого облікового запису.</li>
<li>У разі підозри несанкціонованого доступу негайно повідомте нас на <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>.</li>
<li>Компанія має право призупинити або видалити обліковий запис у разі порушення цих Умов, надання недостовірних даних або тривалої неактивності.</li>
</ul>

<h3>5. Порядок надання Послуг</h3>
<p>Типовий цикл співпраці складається з таких етапів:</p>
<ul>
<li><strong>Заявка.</strong> Замовник подає заявку через Сайт, кабінет, телефон або email, зазначаючи код відходу, орієнтовний обсяг, склад і місце знаходження.</li>
<li><strong>Прорахунок.</strong> Менеджер готує комерційну пропозицію з урахуванням класу небезпеки, логістики та методу утилізації.</li>
<li><strong>Договір.</strong> Сторони укладають Договір (онлайн-підписання через Платформу або паперова форма).</li>
<li><strong>Оплата.</strong> Замовник сплачує рахунок безготівковим переказом за реквізитами IBAN, зазначеними у рахунку.</li>
<li><strong>Вивезення.</strong> Транспортування здійснюється спеціалізованим транспортом, для небезпечних вантажів — з дотриманням вимог ADR.</li>
<li><strong>Утилізація та закриття.</strong> Після виконання робіт Замовник отримує акт про утилізацію/знешкодження та супровідні документи; електронні копії зберігаються у кабінеті.</li>
</ul>

<h3>6. Обов'язки Замовника щодо декларування відходів</h3>
<p>Точність даних про відходи є критично важливою для безпеки людей і довкілля. Замовник зобов'язується:</p>
<ul>
<li>надавати повну та достовірну інформацію про вид, код, клас небезпеки, кількість, агрегатний стан, хімічний склад і властивості відходів;</li>
<li>повідомляти про наявність у відходах речовин, що можуть створювати особливу небезпеку (токсичні, легкозаймисті, реакційноздатні, інфекційні тощо);</li>
<li>забезпечити пакування та маркування відходів відповідно до їх класу небезпеки і погоджених умов передачі;</li>
<li>не передавати відходи, не зазначені у заявці та Договорі, а також відходи, заборонені до приймання;</li>
<li>забезпечити безпечний доступ до місця завантаження та дотримання вимог охорони праці на своїй території.</li>
</ul>
<p>Передача недекларованих чи невідповідно задекларованих відходів може призвести до відмови у прийманні, перерахунку вартості, відшкодування завданих збитків та повідомлення уповноважених органів у випадках, передбачених законом.</p>

<h3>7. Калькулятор та цінові пропозиції</h3>
<p>Калькулятор на Сайті надає <strong>орієнтовний</strong> розрахунок вартості на основі типових тарифів. Результат розрахунку не є офертою і не зобов'язує Компанію. Остаточна ціна визначається у комерційній пропозиції та фіксується Договором і рахунком з урахуванням фактичних характеристик відходів, логістики й обсягів.</p>

<h3>8. Оплата</h3>
<ul>
<li>Розрахунки здійснюються у безготівковій формі за реквізитами, зазначеними у рахунку (IBAN). Основна валюта розрахунків — гривня (UAH).</li>
<li>Рахунок виставляється на підставі укладеного Договору. Призначення платежу слід вказувати так, як зазначено у рахунку.</li>
<li>Після здійснення оплати Замовник може завантажити підтвердження платежу в кабінеті; зарахування підтверджується менеджером.</li>
<li>Строки та порядок повернення коштів (за наявності підстав) визначаються Договором та законодавством України.</li>
</ul>

<h3>9. Електронний документообіг</h3>
<p>Платформа підтримує електронне погодження та підписання документів (договорів, актів). Сторони визнають юридичну силу документів, підписаних із використанням електронних засобів у порядку, погодженому Договором та законодавством України про електронні документи й електронний документообіг. На запит Замовника доступний обмін паперовими оригіналами.</p>

<h3>10. Інтелектуальна власність</h3>
<p>Усі матеріали Сайту — тексти, статті блогу, структура каталогу, елементи дизайну, логотипи, торговельні позначення ECO.NOVA, програмний код — належать Компанії або використовуються на законних підставах і охороняються законодавством про інтелектуальну власність. Без попередньої письмової згоди Компанії заборонено копіювання, відтворення, розповсюдження чи створення похідних матеріалів, за винятком цитування з обов'язковим посиланням на джерело.</p>

<h3>11. Правила допустимого використання</h3>
<p>Користуючись Сайтом, ви зобов'язуєтеся не:</p>
<ul>
<li>вчиняти дії, спрямовані на порушення роботи Сайту, обхід засобів захисту чи отримання несанкціонованого доступу до даних;</li>
<li>використовувати автоматизовані засоби масового збору даних (скрейпінг, парсинг) без письмового дозволу Компанії;</li>
<li>завантажувати шкідливий код, надсилати спам або матеріали, що порушують права третіх осіб;</li>
<li>подавати завідомо неправдиві заявки чи видавати себе за іншу особу/компанію;</li>
<li>використовувати Сайт у будь-який спосіб, що суперечить законодавству України.</li>
</ul>

<h3>12. Відповідальність та її обмеження</h3>
<ul>
<li>Компанія не несе відповідальності за збитки, спричинені наданням Замовником недостовірної інформації про відходи.</li>
<li>Компанія не гарантує безперервну та безпомилкову роботу Сайту; можливі планові й позапланові перерви в обслуговуванні.</li>
<li>Матеріали блогу та довідкова інформація не є професійною юридичною чи екологічною консультацією щодо конкретної ситуації Замовника.</li>
<li>Відповідальність Сторін за Договором визначається Договором та законодавством України. Ніщо в цих Умовах не обмежує відповідальності, яка не може бути обмежена законом.</li>
</ul>

<h3>13. Форс-мажор</h3>
<p>Сторони звільняються від відповідальності за часткове або повне невиконання зобов'язань, якщо воно стало наслідком обставин непереборної сили (воєнні дії, стихійні лиха, акти органів влади, аварії енергомереж тощо), що підтверджуються у порядку, встановленому законодавством України.</p>

<h3>14. Персональні дані</h3>
<p>Обробка персональних даних користувачів Сайту здійснюється відповідно до <a href="/privacy">Політики конфіденційності</a>. Використання файлів cookie описано у <a href="/cookies">Політиці Cookies</a>.</p>

<h3>15. Комунікації та повідомлення</h3>
<p>Погоджуючись з цими Умовами, ви приймаєте, що операційні повідомлення (статуси заявок, рахунки, акти, нагадування про оплату, службові сповіщення безпеки) можуть надсилатися на email, у клієнтський кабінет або телефоном, зазначеними під час реєстрації чи подання заявки. Такі повідомлення є частиною надання Послуг і не є рекламною розсилкою. Повідомлення вважається отриманим у день його надсилання на актуальні контактні дані Замовника; підтримання актуальності контактних даних є обов'язком Замовника.</p>

<h3>16. Доступність сервісу та технічна підтримка</h3>
<ul>
<li>Ми прагнемо забезпечувати доступність Сайту та кабінету в режимі 24/7, однак не гарантуємо відсутність перерв: можливі планові технічні роботи (за можливості — у неробочі години) та позапланові збої.</li>
<li>Технічна підтримка надається у робочі дні в години, зазначені у розділі «Контакти». Звернення обробляються у порядку черговості з пріоритетом для питань безпеки та доступу до кабінету.</li>
<li>Компанія має право змінювати, вдосконалювати або припиняти окремі функції Сайту без попереднього повідомлення, якщо це не погіршує виконання вже укладених Договорів.</li>
</ul>

<h3>17. Відступлення прав</h3>
<p>Замовник не має права передавати свої права та обов'язки за цими Умовами третім особам без попередньої письмової згоди Компанії. Компанія може передати свої права та обов'язки правонаступнику в разі реорганізації за умови збереження рівня захисту даних і виконання чинних Договорів.</p>

<h3>18. Автономність положень та повнота домовленостей</h3>
<p>Якщо окреме положення цих Умов буде визнане недійсним або таким, що не підлягає застосуванню, це не впливає на чинність решти положень. Ці Умови разом із <a href="/privacy">Політикою конфіденційності</a>, <a href="/cookies">Політикою Cookies</a> та укладеними Договорами становлять повну домовленість між вами та Компанією щодо користування Сайтом. У разі розбіжностей між цими Умовами та укладеним Договором пріоритет має Договір.</p>

<h3>19. Мовні версії</h3>
<p>Умови публікуються українською та англійською мовами. У разі розбіжностей між мовними версіями пріоритет має версія українською мовою.</p>

<h3>20. Зміни Умов</h3>
<p>Компанія може періодично оновлювати ці Умови. Нова редакція набирає чинності з моменту публікації на Сайті, якщо не зазначено інше. Продовження користування Сайтом після публікації змін означає згоду з оновленими Умовами. Рекомендуємо періодично переглядати цю сторінку.</p>

<h3>21. Застосовне право та вирішення спорів</h3>
<p>Ці Умови регулюються правом України. Усі спори Сторони намагаються вирішити шляхом переговорів; претензійний порядок: письмова претензія розглядається протягом 20 робочих днів з дня отримання. У разі недосягнення згоди спір передається на розгляд суду за встановленою законодавством України підсудністю.</p>

<h3>22. Контакти</h3>
<p>ТОВ «ЕКО-НОВА»<br/>
Email: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a><br/>
Телефон: +380 66 788 04 45<br/>
Адреса для листування зазначена у розділі «Контакти» Сайту.</p>

<p><em>Дата останнього оновлення: 2 липня 2026 року.</em></p>
"""

TERMS_EN = """
<h2>Terms of Use</h2>
<p>These Terms of Use (the "Terms") govern access to and use of the website and online services of the ECO.NOVA platform (the "Platform", the "Site") operated by ECO-NOVA LLC (the "Company", "we"). By opening the Site, registering an account, submitting a request or using any Platform service, you confirm that you have read, understood and agree to be bound by these Terms. If you do not agree, please stop using the Site.</p>

<h3>1. Definitions</h3>
<ul>
<li><strong>Platform</strong> — the website, client cabinet, cost calculator, waste-code catalog, blog and related ECO.NOVA online services.</li>
<li><strong>Client</strong> — a legal entity or registered individual entrepreneur ordering waste-management services.</li>
<li><strong>Waste</strong> — substances, materials and items generated in the course of the Client's activities that are subject to removal or utilization under the laws of Ukraine.</li>
<li><strong>Waste code</strong> — a classification code under the national waste classifier; every catalog item on the Site is mapped to such a code.</li>
<li><strong>Hazard class</strong> — the degree of hazard of waste (classes 1–4) which determines packaging, transport and treatment requirements.</li>
<li><strong>Services</strong> — acceptance, collection, transportation (including under ADR requirements), storage, treatment, processing, neutralisation and utilization of waste, together with the related documentary support.</li>
<li><strong>Contract</strong> — a separate service agreement concluded between the Company and the Client (e-signed online or in paper form).</li>
<li><strong>Client cabinet</strong> — the secure area of the Platform where the Client manages requests, contracts, invoices and documents.</li>
</ul>

<h3>2. Status of the Platform and nature of information</h3>
<p>The Site provides information about the Company's services, a waste-code catalog with an acceptance matrix, an indicative cost calculator, request forms and a blog with waste-management materials. All information on the Site is for reference only and <strong>does not constitute a public offer</strong> unless expressly stated otherwise. The specific terms of the Services — scope, price, timing, location — are defined exclusively by the Contract.</p>

<h3>3. Licences and permits</h3>
<p>The Company carries out hazardous-waste management activities on the basis of valid licences and permits issued by the authorised bodies of Ukraine and in accordance with the Law of Ukraine "On Waste Management" and related regulations. The list of waste codes the Company is entitled to accept is reflected in the acceptance matrix on the Site. The Company may refuse to accept waste that falls outside its permit documentation.</p>

<h3>4. Account and client cabinet</h3>
<ul>
<li>Registration in the client cabinet is available to business entities (B2B). When registering you must provide accurate company details (name, registration/tax code, contact person, phone, email).</li>
<li>You are responsible for keeping your credentials confidential and for all actions performed under your account.</li>
<li>If you suspect unauthorised access, notify us immediately at <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>.</li>
<li>The Company may suspend or delete an account in case of a breach of these Terms, provision of inaccurate data or prolonged inactivity.</li>
</ul>

<h3>5. Service workflow</h3>
<p>A typical cooperation cycle includes the following stages:</p>
<ul>
<li><strong>Request.</strong> The Client submits a request via the Site, cabinet, phone or email, specifying the waste code, estimated volume, composition and location.</li>
<li><strong>Quotation.</strong> A manager prepares a commercial offer taking into account the hazard class, logistics and treatment method.</li>
<li><strong>Contract.</strong> The parties conclude a Contract (e-signing via the Platform or in paper form).</li>
<li><strong>Payment.</strong> The Client pays the invoice by bank transfer to the IBAN details stated in the invoice.</li>
<li><strong>Collection.</strong> Transportation is performed by specialised vehicles; dangerous goods are carried in compliance with ADR requirements.</li>
<li><strong>Utilization and close-out.</strong> Upon completion the Client receives a utilization/neutralisation act and supporting documents; electronic copies are stored in the cabinet.</li>
</ul>

<h3>6. Client's waste-declaration obligations</h3>
<p>Accuracy of waste data is critical for the safety of people and the environment. The Client undertakes to:</p>
<ul>
<li>provide complete and accurate information on the type, code, hazard class, quantity, physical state, chemical composition and properties of the waste;</li>
<li>disclose the presence of substances posing particular danger (toxic, flammable, reactive, infectious, etc.);</li>
<li>ensure packaging and labelling of the waste according to its hazard class and the agreed hand-over conditions;</li>
<li>not hand over waste not specified in the request and the Contract, or waste prohibited from acceptance;</li>
<li>provide safe access to the loading site and observe occupational-safety requirements on its premises.</li>
</ul>
<p>Handing over undeclared or misdeclared waste may result in refusal of acceptance, price recalculation, compensation of damages and notification of the competent authorities where required by law.</p>

<h3>7. Calculator and quotations</h3>
<p>The on-site calculator provides an <strong>indicative</strong> cost estimate based on standard tariffs. The calculation result is not an offer and does not bind the Company. The final price is set out in the commercial offer and fixed by the Contract and the invoice, taking into account the actual characteristics of the waste, logistics and volumes.</p>

<h3>8. Payment</h3>
<ul>
<li>Settlements are made by bank transfer to the details stated in the invoice (IBAN). The primary settlement currency is the Ukrainian hryvnia (UAH).</li>
<li>Invoices are issued on the basis of a concluded Contract. The payment purpose must be indicated exactly as stated in the invoice.</li>
<li>After payment the Client may upload the payment confirmation in the cabinet; crediting is confirmed by a manager.</li>
<li>Refund terms (where applicable) are governed by the Contract and the laws of Ukraine.</li>
</ul>

<h3>9. Electronic document flow</h3>
<p>The Platform supports electronic approval and signing of documents (contracts, acts). The parties recognise the legal force of documents signed by electronic means in the manner agreed in the Contract and in accordance with Ukrainian legislation on electronic documents and electronic document flow. Paper originals are available upon the Client's request.</p>

<h3>10. Intellectual property</h3>
<p>All Site materials — texts, blog articles, catalog structure, design elements, logos, ECO.NOVA trade designations and program code — belong to the Company or are used on lawful grounds and are protected by intellectual-property law. Copying, reproduction, distribution or creation of derivative materials without the Company's prior written consent is prohibited, except for quotation with mandatory attribution.</p>

<h3>11. Acceptable use</h3>
<p>When using the Site you undertake not to:</p>
<ul>
<li>perform actions aimed at disrupting the Site, bypassing security measures or gaining unauthorised access to data;</li>
<li>use automated bulk data-collection tools (scraping, parsing) without the Company's written permission;</li>
<li>upload malicious code, send spam or materials infringing third-party rights;</li>
<li>submit knowingly false requests or impersonate another person or company;</li>
<li>use the Site in any way that violates the laws of Ukraine.</li>
</ul>

<h3>12. Liability and its limitation</h3>
<ul>
<li>The Company is not liable for damages caused by the Client providing inaccurate information about the waste.</li>
<li>The Company does not guarantee uninterrupted or error-free operation of the Site; scheduled and unscheduled maintenance interruptions are possible.</li>
<li>Blog materials and reference information do not constitute professional legal or environmental advice for the Client's specific situation.</li>
<li>The parties' liability under the Contract is governed by the Contract and the laws of Ukraine. Nothing in these Terms limits liability that cannot be limited by law.</li>
</ul>

<h3>13. Force majeure</h3>
<p>The parties are released from liability for partial or full non-performance of obligations caused by force-majeure circumstances (military action, natural disasters, acts of public authorities, power-grid failures, etc.) confirmed in the manner prescribed by the laws of Ukraine.</p>

<h3>14. Personal data</h3>
<p>Personal data of Site users is processed in accordance with the <a href="/privacy">Privacy Policy</a>. The use of cookies is described in the <a href="/cookies">Cookies Policy</a>.</p>

<h3>15. Communications and notices</h3>
<p>By accepting these Terms you agree that operational notices (request statuses, invoices, acts, payment reminders, security service messages) may be sent to the email address, the client cabinet or the phone number provided during registration or when submitting a request. Such notices form part of the Services and are not marketing communications. A notice is deemed received on the day it is sent to the Client's current contact details; keeping contact details up to date is the Client's responsibility.</p>

<h3>16. Service availability and technical support</h3>
<ul>
<li>We aim to keep the Site and the cabinet available 24/7 but do not guarantee uninterrupted operation: scheduled maintenance (where possible — outside business hours) and unscheduled outages may occur.</li>
<li>Technical support is provided on business days during the hours stated in the Contacts section. Enquiries are handled in order of receipt, with priority for security and cabinet-access issues.</li>
<li>The Company may modify, improve or discontinue individual Site features without prior notice, provided this does not impair the performance of contracts already concluded.</li>
</ul>

<h3>17. Assignment</h3>
<p>The Client may not assign its rights and obligations under these Terms to third parties without the Company's prior written consent. The Company may assign its rights and obligations to a legal successor in the course of a reorganisation, provided the level of data protection is maintained and existing Contracts continue to be performed.</p>

<h3>18. Severability and entire agreement</h3>
<p>If any provision of these Terms is held invalid or unenforceable, the remaining provisions remain in full force. These Terms, together with the <a href="/privacy">Privacy Policy</a>, the <a href="/cookies">Cookies Policy</a> and the concluded Contracts, constitute the entire agreement between you and the Company regarding the use of the Site. In case of a conflict between these Terms and a concluded Contract, the Contract prevails.</p>

<h3>19. Language versions</h3>
<p>The Terms are published in Ukrainian and English. In case of any discrepancy between the language versions, the Ukrainian version prevails.</p>

<h3>20. Changes to the Terms</h3>
<p>The Company may update these Terms from time to time. The new version takes effect upon publication on the Site unless stated otherwise. Continued use of the Site after publication of changes constitutes acceptance of the updated Terms. We recommend reviewing this page periodically.</p>

<h3>21. Governing law and dispute resolution</h3>
<p>These Terms are governed by the law of Ukraine. The parties shall endeavour to resolve all disputes through negotiations; pre-trial procedure: a written claim is considered within 20 business days of receipt. Failing agreement, the dispute shall be referred to the court having jurisdiction under the laws of Ukraine.</p>

<h3>22. Contact</h3>
<p>ECO-NOVA LLC<br/>
Email: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a><br/>
Phone: +380 66 788 04 45<br/>
The mailing address is available in the Contacts section of the Site.</p>

<p><em>Last updated: July 2, 2026.</em></p>
"""

# ═══════════════════════════════════════════════════════════════════════════
#  PRIVACY POLICY
# ═══════════════════════════════════════════════════════════════════════════

PRIVACY_UK = """
<h2>Політика конфіденційності</h2>
<p>Ця Політика конфіденційності (далі — «Політика») пояснює, які персональні дані збирає ТОВ «ЕКО-НОВА» (далі — «Компанія», «ми») під час вашого користування вебсайтом і сервісами платформи ECO.NOVA, з якою метою ми їх обробляємо, кому можемо передавати та які права ви маєте. Обробка здійснюється відповідно до Закону України «Про захист персональних даних», а щодо користувачів з Європейського Союзу — з урахуванням вимог Загального регламенту про захист даних (GDPR).</p>

<h3>1. Володілець персональних даних</h3>
<p>Володільцем персональних даних є ТОВ «ЕКО-НОВА». З питань обробки персональних даних звертайтеся: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>, телефон +380 66 788 04 45.</p>

<h3>2. Сфера дії</h3>
<p>Політика застосовується до даних, зібраних через: публічний вебсайт (форми заявок і зворотного дзвінка, підписка на розсилку, калькулятор), клієнтський кабінет, телефонні звернення (у т.ч. систему кол-трекінгу), електронне листування та месенджери, якими ви звертаєтеся до нас.</p>

<h3>3. Які дані ми збираємо</h3>
<ul>
<li><strong>Ідентифікаційні та контактні дані:</strong> ім'я та прізвище контактної особи, посада, номер телефону, адреса електронної пошти.</li>
<li><strong>Дані про компанію:</strong> назва, код ЄДРПОУ, юридична/фактична адреса, банківські реквізити — у межах, необхідних для укладення та виконання договорів.</li>
<li><strong>Дані заявок і договорів:</strong> зміст звернень, коди та характеристики відходів, обсяги, адреси об'єктів, історія замовлень, документи (договори, рахунки, акти).</li>
<li><strong>Платіжна інформація:</strong> реквізити платежів, підтвердження оплати. Ми не зберігаємо дані банківських карток.</li>
<li><strong>Дані комунікацій:</strong> записи та метадані телефонних дзвінків (номер, час, тривалість) через систему кол-трекінгу, листування електронною поштою та в чатах.</li>
<li><strong>Технічні дані:</strong> IP-адреса, тип пристрою і браузера, мова, сторінки відвідування, джерело переходу, файли cookie та схожі технології (див. <a href="/cookies">Політику Cookies</a>).</li>
<li><strong>Дані облікового запису:</strong> логін (email), хешований пароль, налаштування кабінету, журнал дій із безпеки.</li>
</ul>

<h3>4. Джерела отримання даних</h3>
<ul>
<li>безпосередньо від вас — через форми, кабінет, телефон, email;</li>
<li>автоматично — під час користування Сайтом (технічні дані, cookies);</li>
<li>з відкритих державних реєстрів (наприклад, ЄДР) — для перевірки реквізитів контрагента при укладенні договору.</li>
</ul>

<h3>5. Цілі та правові підстави обробки</h3>
<ul>
<li><strong>Обробка заявок і комунікація</strong> — вчинення дій на вашу вимогу перед укладенням договору; законний інтерес у веденні клієнтських відносин.</li>
<li><strong>Укладення та виконання договорів</strong> — виконання договору: організація вивезення, утилізації, документообіг, виставлення рахунків.</li>
<li><strong>Виконання законодавчих обов'язків</strong> — бухгалтерський і податковий облік, звітність у сфері поводження з відходами, відповіді на запити уповноважених органів.</li>
<li><strong>Робота клієнтського кабінету</strong> — виконання договору про користування сервісом; захист облікових записів (законний інтерес).</li>
<li><strong>Розсилка новин</strong> — ваша згода (яку можна відкликати у будь-який момент за посиланням у листі або звернувшись до нас).</li>
<li><strong>Аналітика та покращення Сайту</strong> — ваша згода на аналітичні cookie; законний інтерес у забезпеченні безпеки та стабільності сервісу.</li>
<li><strong>Кол-трекінг і контроль якості</strong> — законний інтерес в обліку звернень та підвищенні якості обслуговування.</li>
</ul>

<h3>6. Кому ми можемо передавати дані</h3>
<p>Ми не продаємо персональні дані. Передача можлива лише у межах, необхідних для зазначених цілей, таким категоріям отримувачів:</p>
<ul>
<li>логістичні підрядники та перевізники (у т.ч. ADR) — для організації вивезення відходів;</li>
<li>постачальники ІТ-послуг: хостинг, хмарна інфраструктура, сервіси електронної пошти й розсилок, система кол-трекінгу;</li>
<li>банки — у межах здійснення розрахунків;</li>
<li>аудитори, юридичні та бухгалтерські консультанти — на підставі договорів із зобов'язаннями конфіденційності;</li>
<li>державні органи — виключно у випадках і обсязі, передбачених законодавством України.</li>
</ul>
<p>З усіма обробниками укладаються договори, що зобов'язують їх захищати дані та обробляти їх лише за нашими інструкціями.</p>

<h3>7. Транскордонна передача</h3>
<p>Окремі постачальники ІТ-послуг можуть обробляти дані на серверах за межами України (зокрема в ЄС). У таких випадках ми вживаємо заходів, щоб передача відбувалася до юрисдикцій із належним рівнем захисту або із застосуванням відповідних договірних гарантій.</p>

<h3>8. Строки зберігання</h3>
<ul>
<li>дані заявок, що не завершилися договором — до 3 років з моменту останньої взаємодії;</li>
<li>договори, рахунки, акти та пов'язані дані — протягом строку дії договору та строків зберігання первинних документів, встановлених законодавством (як правило, не менше 3 років, для окремих документів — довше);</li>
<li>дані облікового запису — протягом існування облікового запису та до 1 року після його видалення (резервні копії, захист від зловживань);</li>
<li>записи дзвінків — до 12 місяців, якщо довший строк не потрібен для розгляду спору;</li>
<li>технічні журнали (логи) — до 12 місяців;</li>
<li>дані розсилки — до відкликання згоди.</li>
</ul>
<p>Після спливу строків дані видаляються або незворотно знеособлюються.</p>

<h3>9. Захист даних</h3>
<p>Ми застосовуємо організаційні й технічні заходи безпеки: шифрування з'єднань (TLS), зберігання паролів у хешованому вигляді, розмежування прав доступу за ролями, двофакторну автентифікацію для персоналу, журналювання дій в адміністративній частині, резервне копіювання та регулярне оновлення програмного забезпечення. Жоден метод передачі даних не є абсолютно безпечним, однак ми постійно вдосконалюємо наші заходи захисту.</p>

<h3>10. Ваші права</h3>
<p>Відповідно до законодавства ви маєте право:</p>
<ul>
<li>знати про обробку своїх даних та отримати доступ до них;</li>
<li>вимагати виправлення неточних або неповних даних;</li>
<li>вимагати видалення даних, якщо немає законних підстав для їх подальшої обробки;</li>
<li>вимагати обмеження обробки та заперечувати проти обробки, що ґрунтується на законному інтересі;</li>
<li>на перенесення даних, наданих на підставі згоди чи договору;</li>
<li>відкликати згоду у будь-який момент (без впливу на законність обробки до відкликання);</li>
<li>звернутися зі скаргою до Уповноваженого Верховної Ради України з прав людини або до суду.</li>
</ul>
<p>Для реалізації прав напишіть на <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>. Ми відповімо у строк до 30 календарних днів.</p>

<h3>11. Автоматизоване прийняття рішень і профілювання</h3>
<p>Ми не приймаємо рішень, що мають для вас юридичні чи подібні суттєві наслідки, виключно на основі автоматизованої обробки. Орієнтовний розрахунок калькулятора формується автоматично, однак будь-яка комерційна пропозиція, договір чи відмова у прийманні відходів завжди перевіряються та затверджуються працівником Компанії.</p>

<h3>12. Повідомлення про інциденти безпеки</h3>
<p>У разі порушення захисту персональних даних, що може створити високий ризик для ваших прав, ми повідомимо вас та, де це вимагається законом, уповноважений орган без невиправданої затримки після виявлення інциденту, а також вживемо заходів для мінімізації наслідків і недопущення повторення.</p>

<h3>13. Відеоспостереження на об'єктах</h3>
<p>З міркувань безпеки та контролю технологічних процесів на виробничих майданчиках Компанії може здійснюватися відеоспостереження. Про це інформують таблички при вході. Записи використовуються виключно для забезпечення безпеки людей, майна та довкілля, зберігаються обмежений строк (до 30 днів, якщо довший строк не потрібен для розслідування інциденту) та доступні обмеженому колу уповноважених осіб.</p>

<h3>14. Cookies</h3>
<p>Використання файлів cookie та керування згодою описані в окремій <a href="/cookies">Політиці Cookies</a>.</p>

<h3>15. Дані неповнолітніх</h3>
<p>Сервіси Платформи призначені для суб'єктів господарювання та осіб, які досягли 18 років. Ми свідомо не збираємо дані дітей.</p>

<h3>16. Посилання на сторонні ресурси</h3>
<p>Сайт може містити посилання на зовнішні ресурси. Ми не відповідаємо за їхні практики конфіденційності; ознайомлюйтеся з політиками відповідних сайтів.</p>

<h3>17. Зміни Політики</h3>
<p>Ми можемо періодично оновлювати цю Політику. Актуальна редакція завжди доступна на цій сторінці із зазначенням дати оновлення. Про суттєві зміни ми повідомимо додатково (наприклад, банером на Сайті або листом).</p>

<h3>18. Контакти</h3>
<p>ТОВ «ЕКО-НОВА»<br/>
Email: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a><br/>
Телефон: +380 66 788 04 45</p>

<p><em>Дата останнього оновлення: 2 липня 2026 року.</em></p>
"""

PRIVACY_EN = """
<h2>Privacy Policy</h2>
<p>This Privacy Policy (the "Policy") explains what personal data ECO-NOVA LLC (the "Company", "we") collects when you use the ECO.NOVA website and services, why we process it, with whom we may share it and what rights you have. Processing is carried out in accordance with the Law of Ukraine "On Personal Data Protection" and, for users from the European Union, with due regard to the General Data Protection Regulation (GDPR).</p>

<h3>1. Data controller</h3>
<p>The controller of personal data is ECO-NOVA LLC. For any privacy matters contact us at <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a> or +380 66 788 04 45.</p>

<h3>2. Scope</h3>
<p>The Policy applies to data collected via: the public website (request and call-back forms, newsletter subscription, calculator), the client cabinet, phone calls (including the call-tracking system), email correspondence and messengers you use to contact us.</p>

<h3>3. Data we collect</h3>
<ul>
<li><strong>Identity and contact data:</strong> contact person's name and surname, position, phone number, email address.</li>
<li><strong>Company data:</strong> name, registration/tax code, legal/actual address, bank details — to the extent necessary for concluding and performing contracts.</li>
<li><strong>Request and contract data:</strong> content of enquiries, waste codes and characteristics, volumes, site addresses, order history, documents (contracts, invoices, acts).</li>
<li><strong>Payment information:</strong> payment references and confirmations. We do not store bank-card data.</li>
<li><strong>Communication data:</strong> recordings and metadata of phone calls (number, time, duration) via the call-tracking system, email and chat correspondence.</li>
<li><strong>Technical data:</strong> IP address, device and browser type, language, pages visited, referral source, cookies and similar technologies (see the <a href="/cookies">Cookies Policy</a>).</li>
<li><strong>Account data:</strong> login (email), hashed password, cabinet preferences, security activity log.</li>
</ul>

<h3>4. Sources of data</h3>
<ul>
<li>directly from you — via forms, the cabinet, phone, email;</li>
<li>automatically — while you use the Site (technical data, cookies);</li>
<li>from open state registers — to verify counterparty details when concluding a contract.</li>
</ul>

<h3>5. Purposes and legal bases</h3>
<ul>
<li><strong>Processing requests and communication</strong> — steps taken at your request prior to entering into a contract; legitimate interest in managing client relations.</li>
<li><strong>Conclusion and performance of contracts</strong> — performance of a contract: arranging collection and utilization, document flow, invoicing.</li>
<li><strong>Compliance with legal obligations</strong> — accounting and tax records, waste-management reporting, responses to lawful requests of authorities.</li>
<li><strong>Operation of the client cabinet</strong> — performance of the service agreement; account protection (legitimate interest).</li>
<li><strong>Newsletter</strong> — your consent (withdrawable at any time via the unsubscribe link or by contacting us).</li>
<li><strong>Analytics and Site improvement</strong> — your consent to analytics cookies; legitimate interest in the security and stability of the service.</li>
<li><strong>Call tracking and quality control</strong> — legitimate interest in recording enquiries and improving service quality.</li>
</ul>

<h3>6. Recipients of data</h3>
<p>We do not sell personal data. Sharing is limited to what is necessary for the purposes above, with the following categories of recipients:</p>
<ul>
<li>logistics contractors and carriers (including ADR) — to arrange waste collection;</li>
<li>IT service providers: hosting, cloud infrastructure, email and newsletter services, the call-tracking system;</li>
<li>banks — within payment processing;</li>
<li>auditors, legal and accounting advisers — under contracts with confidentiality obligations;</li>
<li>public authorities — only in the cases and to the extent required by the laws of Ukraine.</li>
</ul>
<p>All processors are bound by agreements obliging them to protect the data and process it only on our instructions.</p>

<h3>7. International transfers</h3>
<p>Certain IT providers may process data on servers outside Ukraine (including in the EU). In such cases we ensure the transfer is made to jurisdictions with an adequate level of protection or subject to appropriate contractual safeguards.</p>

<h3>8. Retention periods</h3>
<ul>
<li>request data that did not result in a contract — up to 3 years from the last interaction;</li>
<li>contracts, invoices, acts and related data — for the term of the contract and the statutory retention periods for primary documents (generally at least 3 years; longer for certain documents);</li>
<li>account data — for the life of the account and up to 1 year after its deletion (backups, abuse prevention);</li>
<li>call recordings — up to 12 months, unless a longer period is needed for dispute resolution;</li>
<li>technical logs — up to 12 months;</li>
<li>newsletter data — until consent is withdrawn.</li>
</ul>
<p>Upon expiry, data is deleted or irreversibly anonymised.</p>

<h3>9. Data security</h3>
<p>We apply organisational and technical safeguards: encrypted connections (TLS), hashed password storage, role-based access control, two-factor authentication for staff, audit logging in the administrative area, backups and regular software updates. No method of data transmission is completely secure, but we continuously improve our protection measures.</p>

<h3>10. Your rights</h3>
<p>Under applicable law you have the right to:</p>
<ul>
<li>know about the processing of your data and obtain access to it;</li>
<li>request rectification of inaccurate or incomplete data;</li>
<li>request erasure where there is no lawful ground for further processing;</li>
<li>request restriction of processing and object to processing based on legitimate interest;</li>
<li>data portability for data provided on the basis of consent or a contract;</li>
<li>withdraw consent at any time (without affecting the lawfulness of prior processing);</li>
<li>lodge a complaint with the Ukrainian Parliament Commissioner for Human Rights or with a court; EU users may also contact their local supervisory authority.</li>
</ul>
<p>To exercise your rights, write to <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>. We respond within 30 calendar days.</p>

<h3>11. Automated decision-making and profiling</h3>
<p>We do not make decisions producing legal or similarly significant effects for you based solely on automated processing. The calculator's indicative estimate is generated automatically, but any commercial offer, contract or refusal to accept waste is always reviewed and approved by a Company employee.</p>

<h3>12. Security incident notification</h3>
<p>In the event of a personal-data breach likely to result in a high risk to your rights, we will notify you and, where required by law, the competent authority without undue delay after becoming aware of the incident, and will take measures to mitigate the consequences and prevent recurrence.</p>

<h3>13. CCTV at facilities</h3>
<p>For safety and process-control reasons, video surveillance may operate at the Company's production sites. Signs at the entrances provide notice. Recordings are used solely to ensure the safety of people, property and the environment, are retained for a limited period (up to 30 days unless a longer period is needed for an incident investigation) and are accessible to a restricted circle of authorised personnel.</p>

<h3>14. Cookies</h3>
<p>The use of cookies and consent management are described in the separate <a href="/cookies">Cookies Policy</a>.</p>

<h3>15. Children's data</h3>
<p>The Platform is intended for business entities and persons aged 18 or over. We do not knowingly collect children's data.</p>

<h3>16. Third-party links</h3>
<p>The Site may contain links to external resources. We are not responsible for their privacy practices; please review the policies of the respective sites.</p>

<h3>17. Changes to this Policy</h3>
<p>We may update this Policy from time to time. The current version is always available on this page with the date of the update. We will additionally notify you of material changes (e.g., by a banner on the Site or by email).</p>

<h3>18. Contact</h3>
<p>ECO-NOVA LLC<br/>
Email: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a><br/>
Phone: +380 66 788 04 45</p>

<p><em>Last updated: July 2, 2026.</em></p>
"""

# ═══════════════════════════════════════════════════════════════════════════
#  COOKIES POLICY
# ═══════════════════════════════════════════════════════════════════════════

COOKIES_UK = """
<h2>Політика Cookies</h2>
<p>Ця Політика Cookies пояснює, що таке файли cookie, які саме cookie та схожі технології використовує вебсайт ECO.NOVA, з якою метою, як довго вони зберігаються та як ви можете керувати своїм вибором. Політика є частиною нашої <a href="/privacy">Політики конфіденційності</a>.</p>

<h3>1. Що таке cookies</h3>
<p>Cookies — це невеликі текстові файли, які вебсайт зберігає на вашому пристрої (комп'ютері, планшеті, смартфоні) під час відвідування. Вони допомагають сайту «пам'ятати» ваші дії та налаштування (мову, сесію входу, згоду на cookies) упродовж певного часу. Окрім cookies, можуть використовуватися схожі технології — localStorage та sessionStorage браузера; у цій Політиці ми називаємо їх узагальнено «cookies».</p>

<h3>2. Категорії cookies, які ми використовуємо</h3>
<p><strong>2.1. Необхідні (завжди активні).</strong> Забезпечують базову роботу Сайту; без них сервіс не функціонуватиме коректно. Згода на них не вимагається.</p>
<ul>
<li><strong>eco_cookie_consent</strong> — зберігає ваш вибір щодо cookies (усі / лише необхідні); строк — до 12 місяців;</li>
<li><strong>токен сесії кабінету</strong> — підтримує безпечний вхід у клієнтський кабінет/CRM; строк — сесія або до виходу з облікового запису;</li>
<li><strong>мовні налаштування</strong> — запам'ятовують обрану мову інтерфейсу (укр/англ); строк — до 12 місяців;</li>
<li><strong>службові cookie безпеки</strong> — захист від підробки запитів та зловживань; строк — сесія.</li>
</ul>
<p><strong>2.2. Аналітичні (за вашою згодою).</strong> Допомагають зрозуміти, як відвідувачі користуються Сайтом (які сторінки відвідують, звідки переходять, які дії виконують), щоб покращувати структуру, контент і сервіс. Дані обробляються в узагальненому вигляді та не використовуються для показу реклами. Строк зберігання аналітичних ідентифікаторів — до 24 місяців.</p>
<p><strong>2.3. Кол-трекінг (за вашою згодою).</strong> Для обліку телефонних звернень може використовуватися технологія підміни номерів, яка застосовує cookie для зв'язування вашого візиту з дзвінком. Це допомагає нам розуміти, з якої сторінки ви зателефонували, та підвищувати якість обслуговування.</p>
<p><strong>2.4. Маркетингові.</strong> Наразі ми <strong>не використовуємо</strong> рекламних/таргетингових cookies третіх сторін. У разі їх запровадження ця Політика буде оновлена, а банер згоди — доповнений відповідною категорією.</p>

<h3>3. Типи cookies за строком дії та походженням</h3>
<ul>
<li><strong>Сесійні cookies</strong> — існують лише протягом сеансу роботи з браузером і видаляються після його закриття (наприклад, службові cookie безпеки).</li>
<li><strong>Постійні cookies</strong> — зберігаються на пристрої визначений строк (від кількох днів до 24 місяців) або до видалення вручну (наприклад, вибір мови чи згода на cookies).</li>
<li><strong>Власні (first-party)</strong> — встановлюються безпосередньо доменом ECO.NOVA; саме до цієї категорії належить абсолютна більшість наших cookies.</li>
<li><strong>Сторонні (third-party)</strong> — встановлюються доменами інших постачальників (аналітика, кол-трекінг) і лише після вашої згоди, коли цього вимагає закон.</li>
</ul>

<h3>4. Детальний перелік технологій, які ми використовуємо</h3>
<p>Нижче наведено фактичний перелік записів, які Платформа зберігає на вашому пристрої:</p>
<ul>
<li><strong>eco_cookie_consent</strong> (localStorage) — ваш вибір щодо категорій cookies (усі / лише необхідні) та дата надання згоди; строк — до 12 місяців, після чого банер згоди з'явиться повторно;</li>
<li><strong>eco_lang / мовне налаштування</strong> (localStorage) — обрана мова інтерфейсу (укр/англ); строк — до 12 місяців;</li>
<li><strong>токен сесії клієнтського кабінету</strong> (cookie/localStorage) — підтримує безпечний вхід Замовника; строк — сесія або до виходу з облікового запису;</li>
<li><strong>токен сесії CRM</strong> — робочий доступ персоналу до операційної консолі; строк — обмежений, з автоматичним завершенням сесії;</li>
<li><strong>службові анти-CSRF ідентифікатори</strong> — захист форм від підроблених запитів; строк — сесія;</li>
<li><strong>аналітичні ідентифікатори</strong> (за згодою) — знеособлений ідентифікатор відвідувача для статистики відвідувань; строк — до 24 місяців;</li>
<li><strong>cookie кол-трекінгу</strong> (за згодою) — зв'язує показаний вам підмінний номер телефону з вашим візитом; строк — до 30 днів.</li>
</ul>
<p>Перелік може незначно змінюватися з розвитком Платформи; суттєві зміни відображаються у цій Політиці.</p>

<h3>5. Керування згодою</h3>
<ul>
<li>Під час першого візиту на Сайт з'являється банер, у якому ви можете «Прийняти всі» cookies або обрати «Лише необхідні».</li>
<li>Ваш вибір зберігається до 12 місяців, після чого ми запитаємо згоду повторно.</li>
<li>Змінити свій вибір можна у будь-який момент: очистіть cookies/дані цього сайту в налаштуваннях браузера — і банер з'явиться знову під час наступного візиту.</li>
<li>Відкликання згоди не впливає на законність обробки, здійсненої до відкликання.</li>
</ul>

<h3>6. Керування cookies у браузері</h3>
<p>Ви можете видаляти чи блокувати cookies у налаштуваннях свого браузера:</p>
<ul>
<li><strong>Chrome:</strong> Налаштування → Конфіденційність і безпека → Файли cookie;</li>
<li><strong>Firefox:</strong> Налаштування → Приватність і захист → Куки та дані сайтів;</li>
<li><strong>Safari:</strong> Параметри → Конфіденційність → Керувати даними вебсайтів;</li>
<li><strong>Edge:</strong> Налаштування → Файли cookie та дозволи сайтів.</li>
</ul>
<p>Зауважте: блокування необхідних cookies може призвести до некоректної роботи Сайту (неможливість входу в кабінет, скидання мовних налаштувань, повторна поява банера згоди).</p>

<h3>7. Cookies третіх сторін</h3>
<p>Окремі функції можуть завантажувати ресурси сторонніх постачальників (наприклад, аналітичну платформу чи сервіс кол-трекінгу). Такі постачальники можуть встановлювати власні cookies відповідно до своїх політик. Ми підключаємо сторонні сервіси лише в обсязі, необхідному для роботи відповідної функції, та лише після вашої згоди, коли цього вимагає закон.</p>

<h3>8. Сигнали Do Not Track та Global Privacy Control</h3>
<p>Деякі браузери дозволяють надсилати сигнали «Do Not Track» (DNT) або «Global Privacy Control» (GPC). Наразі єдиного галузевого стандарту реагування на такі сигнали не існує, тому Сайт орієнтується насамперед на ваш вибір у банері згоди. Якщо ви обрали «Лише необхідні», аналітичні та кол-трекінг cookies не встановлюються незалежно від налаштувань DNT/GPC.</p>

<h3>9. Наслідки відмови від cookies</h3>
<ul>
<li><strong>Відмова від необхідних</strong> (через налаштування браузера) — вхід у клієнтський кабінет і збереження налаштувань можуть не працювати; банер згоди з'являтиметься при кожному візиті.</li>
<li><strong>Відмова від аналітичних</strong> — жодних обмежень функціональності; ми лише не отримаємо знеособленої статистики, яка допомагає покращувати Сайт.</li>
<li><strong>Відмова від кол-трекінгу</strong> — телефонний зв'язок працюватиме як звичайно; ми лише не зможемо пов'язати дзвінок зі сторінкою, з якої ви телефонували.</li>
</ul>

<h3>10. Оновлення Політики</h3>
<p>Ми можемо оновлювати цю Політику в разі зміни використовуваних технологій чи вимог законодавства. Актуальна редакція завжди доступна на цій сторінці. Дата останнього оновлення зазначена наприкінці документа; за суттєвих змін ми повторно запитаємо вашу згоду через банер.</p>

<h3>11. Контакти</h3>
<p>Питання щодо використання cookies надсилайте на <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>. Додатково див. <a href="/privacy">Політику конфіденційності</a> та <a href="/terms">Умови використання</a>.</p>

<p><em>Дата останнього оновлення: 2 липня 2026 року.</em></p>
"""

COOKIES_EN = """
<h2>Cookies Policy</h2>
<p>This Cookies Policy explains what cookies are, which cookies and similar technologies the ECO.NOVA website uses, for what purposes, how long they are stored and how you can manage your choice. This Policy forms part of our <a href="/privacy">Privacy Policy</a>.</p>

<h3>1. What cookies are</h3>
<p>Cookies are small text files that a website stores on your device (computer, tablet, smartphone) when you visit it. They help the site "remember" your actions and preferences (language, login session, cookie consent) for a period of time. Besides cookies, similar technologies may be used — the browser's localStorage and sessionStorage; in this Policy we refer to them collectively as "cookies".</p>

<h3>2. Categories of cookies we use</h3>
<p><strong>2.1. Essential (always active).</strong> They enable the core operation of the Site; without them the service will not work correctly. Consent is not required for these.</p>
<ul>
<li><strong>eco_cookie_consent</strong> — stores your cookie choice (all / necessary only); lifetime — up to 12 months;</li>
<li><strong>cabinet session token</strong> — maintains secure sign-in to the client cabinet/CRM; lifetime — session or until you sign out;</li>
<li><strong>language preference</strong> — remembers the selected interface language (UK/EN); lifetime — up to 12 months;</li>
<li><strong>security service cookies</strong> — protection against request forgery and abuse; lifetime — session.</li>
</ul>
<p><strong>2.2. Analytics (with your consent).</strong> They help us understand how visitors use the Site (pages visited, referral sources, actions taken) so we can improve its structure, content and service. The data is processed in aggregate form and is not used to serve advertising. Analytics identifiers are stored for up to 24 months.</p>
<p><strong>2.3. Call tracking (with your consent).</strong> To account for phone enquiries, a number-substitution technology may be used which sets a cookie linking your visit to your call. This helps us understand which page you called from and improve service quality.</p>
<p><strong>2.4. Marketing.</strong> We currently do <strong>not</strong> use third-party advertising/targeting cookies. Should this change, this Policy will be updated and the consent banner extended with the corresponding category.</p>

<h3>3. Types of cookies by lifetime and origin</h3>
<ul>
<li><strong>Session cookies</strong> — exist only for the duration of your browser session and are deleted when you close it (e.g., security service cookies).</li>
<li><strong>Persistent cookies</strong> — remain on the device for a defined period (from a few days up to 24 months) or until deleted manually (e.g., language choice or cookie consent).</li>
<li><strong>First-party</strong> — set directly by the ECO.NOVA domain; the vast majority of our cookies fall into this category.</li>
<li><strong>Third-party</strong> — set by other providers' domains (analytics, call tracking) and only after your consent where required by law.</li>
</ul>

<h3>4. Detailed inventory of the technologies we use</h3>
<p>Below is the actual list of records the Platform stores on your device:</p>
<ul>
<li><strong>eco_cookie_consent</strong> (localStorage) — your choice of cookie categories (all / necessary only) and the consent date; lifetime — up to 12 months, after which the consent banner reappears;</li>
<li><strong>eco_lang / language preference</strong> (localStorage) — the selected interface language (UK/EN); lifetime — up to 12 months;</li>
<li><strong>client-cabinet session token</strong> (cookie/localStorage) — maintains the Client's secure sign-in; lifetime — session or until sign-out;</li>
<li><strong>CRM session token</strong> — staff access to the operations console; lifetime — limited, with automatic session expiry;</li>
<li><strong>anti-CSRF service identifiers</strong> — protect forms against forged requests; lifetime — session;</li>
<li><strong>analytics identifiers</strong> (with consent) — a pseudonymised visitor identifier for usage statistics; lifetime — up to 24 months;</li>
<li><strong>call-tracking cookie</strong> (with consent) — links the substituted phone number shown to you with your visit; lifetime — up to 30 days.</li>
</ul>
<p>The list may change slightly as the Platform evolves; material changes are reflected in this Policy.</p>

<h3>5. Managing consent</h3>
<ul>
<li>On your first visit a banner appears where you can "Accept all" cookies or choose "Only necessary".</li>
<li>Your choice is stored for up to 12 months, after which we will ask for consent again.</li>
<li>You can change your choice at any time: clear this site's cookies/site data in your browser settings — the banner will appear again on your next visit.</li>
<li>Withdrawing consent does not affect the lawfulness of processing carried out before the withdrawal.</li>
</ul>

<h3>6. Managing cookies in your browser</h3>
<p>You can delete or block cookies in your browser settings:</p>
<ul>
<li><strong>Chrome:</strong> Settings → Privacy and security → Cookies;</li>
<li><strong>Firefox:</strong> Settings → Privacy &amp; Security → Cookies and Site Data;</li>
<li><strong>Safari:</strong> Preferences → Privacy → Manage Website Data;</li>
<li><strong>Edge:</strong> Settings → Cookies and site permissions.</li>
</ul>
<p>Please note: blocking essential cookies may cause the Site to malfunction (inability to sign in to the cabinet, loss of language preference, repeated appearance of the consent banner).</p>

<h3>7. Third-party cookies</h3>
<p>Certain features may load resources of third-party providers (for example, an analytics platform or a call-tracking service). Such providers may set their own cookies in accordance with their policies. We connect third-party services only to the extent necessary for the given feature and only after your consent where required by law.</p>

<h3>8. Do Not Track and Global Privacy Control signals</h3>
<p>Some browsers can send "Do Not Track" (DNT) or "Global Privacy Control" (GPC) signals. As there is currently no uniform industry standard for responding to these signals, the Site relies primarily on your choice in the consent banner. If you selected "Only necessary", analytics and call-tracking cookies are not set regardless of your DNT/GPC settings.</p>

<h3>9. Consequences of refusing cookies</h3>
<ul>
<li><strong>Refusing essential cookies</strong> (via browser settings) — signing in to the client cabinet and saving preferences may stop working; the consent banner will appear on every visit.</li>
<li><strong>Refusing analytics cookies</strong> — no loss of functionality; we simply will not receive the aggregated statistics that help us improve the Site.</li>
<li><strong>Refusing call-tracking cookies</strong> — phone contact works as usual; we just cannot link your call to the page you called from.</li>
</ul>

<h3>10. Updates to this Policy</h3>
<p>We may update this Policy when the technologies we use or legal requirements change. The current version is always available on this page. The date of the last update is stated at the end of the document; in case of material changes we will ask for your consent again via the banner.</p>

<h3>11. Contact</h3>
<p>Questions about the use of cookies: <a href="mailto:Econova2013@ukr.net">Econova2013@ukr.net</a>. See also the <a href="/privacy">Privacy Policy</a> and the <a href="/terms">Terms of Use</a>.</p>

<p><em>Last updated: July 2, 2026.</em></p>
"""

# ═══════════════════════════════════════════════════════════════════════════
#  SERVICE CONDITIONS (internal key "conditions")
# ═══════════════════════════════════════════════════════════════════════════

CONDITIONS_UK = """
<h2>Умови послуги</h2>
<p>ECO.NOVA надає повний цикл поводження з небезпечними відходами (класи небезпеки 1–4): приймання за матрицею дозволених кодів, транспортування спеціалізованим транспортом (ADR), сортування, перероблення, знешкодження та утилізацію з повним документальним супроводом — договір, рахунок, акт утилізації.</p>
<ul>
<li>Приймаються лише відходи, включені до дозвільної документації Компанії (див. каталог і матрицю приймання).</li>
<li>Остаточні умови — обсяг, ціна, строки, місце — фіксуються Договором.</li>
<li>Замовник зобов'язаний достовірно задекларувати відходи (код, клас, склад, обсяг).</li>
<li>Розрахунки — безготівкові (IBAN), основна валюта — UAH.</li>
<li>Після завершення робіт Замовник отримує акт та супровідні документи; електронні копії — у клієнтському кабінеті.</li>
</ul>
<p>Повні правила користування Платформою наведено в <a href="/terms">Умовах використання</a>.</p>
"""

CONDITIONS_EN = """
<h2>Service Conditions</h2>
<p>ECO.NOVA provides a full hazardous-waste handling cycle (hazard classes 1–4): acceptance under the permitted-codes matrix, transportation by specialised vehicles (ADR), sorting, processing, neutralisation and utilization with complete documentary support — contract, invoice, utilization act.</p>
<ul>
<li>Only waste included in the Company's permit documentation is accepted (see the catalog and acceptance matrix).</li>
<li>The final terms — volume, price, timing, location — are fixed by the Contract.</li>
<li>The Client must accurately declare the waste (code, class, composition, volume).</li>
<li>Settlements are cashless (IBAN); the primary currency is UAH.</li>
<li>Upon completion the Client receives the act and supporting documents; electronic copies are available in the client cabinet.</li>
</ul>
<p>The full Platform rules are set out in the <a href="/terms">Terms of Use</a>.</p>
"""

# ═══════════════════════════════════════════════════════════════════════════
#  Canonical structure consumed by content.py and the sync script
# ═══════════════════════════════════════════════════════════════════════════

LEGAL_POLICIES = {
    "privacy": {
        "uk": {"title": "Політика конфіденційності", "content": PRIVACY_UK.strip()},
        "en": {"title": "Privacy Policy", "content": PRIVACY_EN.strip()},
    },
    "terms": {
        "uk": {"title": "Умови використання", "content": TERMS_UK.strip()},
        "en": {"title": "Terms of Use", "content": TERMS_EN.strip()},
    },
    "cookies": {
        "uk": {"title": "Політика Cookies", "content": COOKIES_UK.strip()},
        "en": {"title": "Cookies Policy", "content": COOKIES_EN.strip()},
    },
    "conditions": {
        "uk": {"title": "Умови послуги", "content": CONDITIONS_UK.strip()},
        "en": {"title": "Service Conditions", "content": CONDITIONS_EN.strip()},
    },
}
