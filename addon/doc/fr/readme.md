# Braille Extender

Extension NVDA qui étend la sortie et la saisie braille, le défilement et les commandes propres à l’afficheur.

- **Auteurs :** André-Abush Clause et contributeurs
- **Licence :** GNU General Public License v2
- **Version stable :** [Télécharger (canal stable)](https://andreabc.net/projects/NVDA_addons/BrailleExtender/latest)
- **Version de développement :** [Télécharger (canal dev)](https://andreabc.net/projects/NVDA_addons/BrailleExtender/latest?channel=dev)
- **Sources :** [GitHub — BrailleExtender](https://github.com/aaclause/BrailleExtender/)

**NVDA minimum :** 2024.1

Après l’installation de l’extension, vous pouvez lire ce même guide depuis NVDA : **Guide de l’utilisateur** dans le menu NVDA sous Braille Extender, ou **Aide** dans le Gestionnaire d’extensions lorsque Braille Extender est sélectionné.

---

## Table des matières

1. [Documentation dans NVDA](#documentation-dans-nvda)
2. [Démarrage rapide](#demarrage-rapide)
3. [Braille Extender et NVDA](#braille-extender-et-nvda)
4. [Catégories de paramètres (aperçu)](#categories-de-parametres-apercu)
5. [Sujets détaillés](#sujets-detailles)
6. [Fonctionnalités principales](#fonctionnalites-principales)
7. [Commandes et profils](#commandes-et-profils)
8. [Retours et contributions](#retours-et-contributions)
9. [Remerciements](#remerciements)

---

## Documentation dans NVDA

| Élément | Où le trouver |
|--------|----------------|
| **Ce guide (page web)** | **Menu NVDA → Braille Extender → Guide de l’utilisateur**, ou **Gestionnaire d’extensions → Braille Extender → Aide**. |
| **Gestes pour votre afficheur** | **Menu NVDA → Braille Extender → Gestes pour cet afficheur…** — liste basée sur le profil braille actuel et les raccourcis clavier de l’extension. |
| **Tables braille personnalisées** | **Menu NVDA → Braille Extender → Tables braille personnalisées…** (NVDA 2024.3+), ou **Paramètres Braille Extender → Tables braille → Gérer les tables braille personnalisées…**. |
| **Dictionnaires de table** | **Menu NVDA → Braille Extender → Dictionnaires de table** (Global, Table, Temporaire — pas un onglet des paramètres). |
| **Lancements rapides** | **Menu NVDA → Braille Extender → Lancements rapides…** (pas un onglet des paramètres). |
| **Dictionnaire du mode de saisie avancée** | **Menu NVDA → Braille Extender → Dictionnaire du mode de saisie avancée…** (pas un onglet des paramètres). |
| **Sur le web** | Cette page sur GitHub ou le site du projet, si vous la consultez en ligne. |

NVDA ouvre le fichier **`readme.html`** correspondant à votre langue d’interface : d’abord la langue complète (par ex. `fr`), puis le code à deux lettres (`fr`), puis l’anglais (`en`) si aucune traduction n’est installée. Le fichier se trouve dans le dossier **`doc`** de l’extension (`doc/fr/readme.html` pour le français).

---

## Démarrage rapide

1. **Installez** l’extension (fichier `.nvda-addon`, ou l’Add-on Store NVDA lorsqu’elle y est listée).
2. **Guide de l’utilisateur :** **Menu NVDA → Braille Extender → Guide de l’utilisateur** ouvre ce document dans le navigateur. Utilisez-le en explorant les paramètres et les commandes. Le tableau [Documentation dans NVDA](#documentation-dans-nvda) liste les autres entrées du menu.
3. **Paramètres :** **Menu NVDA → Braille Extender → Paramètres…** — parcourez les onglets utiles (par ex. **Général**, **Tables braille**, **Mise en forme des documents**).
4. **Commandes :** **NVDA → Préférences → Touches de commandes → Catégorie : Braille Extender** — assignez les commandes que vous utiliserez. **Menu NVDA → Braille Extender → Gestes pour cet afficheur…** montre ce que définit déjà le profil de votre afficheur.

---

## Braille Extender et NVDA

Braille Extender couvrait autrefois beaucoup de fonctions que **NVDA ne proposait pas encore** en braille. La première version publique date d’**août 2017**, la même semaine que **NVDA 2017.3**.

Les **Paramètres → Braille** de NVDA (et panneaux associés) ont depuis gagné des options dont beaucoup dépendaient de l’extension. Braille Extender ajoute encore du comportement ; consultez les **notes de version** NVDA pour le libellé exact de chaque élément ci-dessous.

| Depuis NVDA | Désormais dans NVDA (résumé) |
|-------------|------------------------------|
| **2022.3** | **Interruption de la parole** lors du défilement de l’afficheur braille. |
| **2024.2** | **`NVDA+Alt+t`** bascule le **mode braille** ; nouveau mode **sortie parole** (le braille reflète ce que NVDA annonce). |
| **2024.3** | **Normalisation Unicode** pour la parole et le braille ; **tables braille personnalisées** depuis les extensions et le dossier scratchpad NVDA. Braille Extender peut ajouter ses tables et utiliser celles d’autres extensions, pas seulement la liste intégrée NVDA. |
| **2024.4** | **Annoncer le caractère lors du routage** dans le texte ; plus de choix de **mise en forme en braille** (ex. balises) ; **début de paragraphe** en braille en lecture par paragraphe ; corrections de routage. |
| **2025.1** | Les **tables d’entrée et de sortie** peuvent suivre la **langue de l’interface** NVDA ; **annoncer la ligne ou le paragraphe** avec les touches de **navigation** braille. |

---

## Catégories de paramètres (aperçu)

Correspondance avec les onglets de **Paramètres Braille Extender** :

| Catégorie | Résumé |
|-----------|--------|
| **Général** | Canal de mise à jour, annoncer la ligne courante au défilement, ignorer les lignes vides, Caps Lock intelligent, retour modificateurs/volume, deux afficheurs favoris et rechargement, marge droite, inversion du défilement, terminaux (braille suit la revue), comportement du curseur au routage, annoncer le caractère au routage (jusqu’à prise en charge par NVDA). |
| **Rotor** | Éléments du rotor et leur ordre. |
| **Défilement automatique** | Délais et comportement du défilement braille automatique. |
| **Mode historique de parole** | Taille de l’historique, numérotation, parole optionnelle en parcourant l’historique. |
| **Mise en forme des documents** | Apparence en braille du gras, liens, alignement, etc., en complément de la mise en forme NVDA (voir [Mise en forme des documents](#mise-en-forme-des-documents)). |
| **Excel** | Valeurs et formules des cellules en braille ; aperçu ligne/colonne optionnel avec routage (voir [Excel](#excel)). |
| **Documents virtuels** | Afficher une **ligne de tableau entière sur une ligne braille** en mode navigation sur les pages web (voir [Documents virtuels (tableaux web)](#documents-virtuels-tableaux-web)). |
| **Présentation des objets** | Ordre nom, état, valeur, etc. sur la ligne focalisée ; surbrillance de la sélection avec points 7/8 ; barres de progression sur l’afficheur. |
| **Tables braille** | Listes préférées entrée/sortie, tables automatiques sur NVDA 2025.1+, table d’entrée pour raccourcis, seconde passe de traduction, tabulations en espaces, **Gérer les tables braille personnalisées…** (NVDA 2024.3+). |
| **Représentation des caractères non définis** | Caractères absents de la table (points, nombres, descriptions, HUC, …). |
| **Mode de saisie avancée** | Signe d’échappement et sortie après un caractère (le dictionnaire d’abréviations est un dialogue menu séparé — voir [Documentation dans NVDA](#documentation-dans-nvda)). |
| **Mode unimanuel** | Activation et choix parmi trois méthodes de saisie unimanuelle. |
| **Libellés de rôles** | Libellés braille personnalisés pour rôles, repères et états. |
| **Avancé** | Correction curseur avec sélecteurs de variation ; actualiser le braille quand le nom de l’objet au premier plan change. |

---

## Sujets détaillés

### Général

- **Mises à jour :** canal stable ou développement ; vérifications automatiques ou manuelles.
- **Dire la ligne courante au défilement :** annonce la ligne quand vous faites défiler l’afficheur — **focalisation**, **revue**, **les deux** ou **désactivé**. Sur **NVDA 2025.1+**, NVDA peut aussi annoncer la ligne avec les touches de navigation braille ; en cas de **double** annonce, désactivez NVDA **Braille → Annoncer lors de la navigation par ligne ou paragraphe** ou réduisez le chevauchement ici.
- **Interrompre la parole au défilement :** la case **Interrompre la parole au défilement sur la même ligne** est **désactivée sur NVDA 2022.3 et ultérieur** ; utilisez NVDA **Braille → Interrompre la parole pendant le défilement**. Sur **NVDA plus ancien**, la case de l’extension reste modifiable.
- **Ignorer les lignes vides :** au défilement ligne par ligne, les lignes vides peuvent être ignorées.
- **Caps Lock intelligent :** si l’option est **activée** et **Caps Lock Windows** aussi, les lettres saisies au **clavier braille** dans un **champ de texte** ordinaire sont **envoyées avec la casse inversée** (chaque **A–Z** prend l’autre casse ; les autres caractères sont inchangés). S’applique à la saisie normale, pas aux raccourcis avec **modificateurs**. Désactivez pour garder la sortie exacte de la table, quelle que soit la casse de Caps Lock.
- **Retour modificateurs / volume :** **braille**, **parole**, **les deux** ou **aucun** pour les verrouillages de modificateurs ou les touches de volume ; **bips** optionnels avec les modificateurs.
- **Deux afficheurs favoris :** choisissez deux noms d’afficheur enregistrés et basculez rapidement avec les commandes de rechargement.
- **Marge droite :** par modèle d’afficheur actif, en cellules (jusqu’à **80** dans le profil ; le contrôle des paramètres peut autoriser une valeur plus haute).
- **Inverser les touches de défilement :** échange « défilement arrière » et « défilement avant ».
- **Terminaux (braille suit la revue) :** si **activé**, dans un **terminal** (Invite de commandes, PowerShell, PuTTY, **Windows Terminal**, etc.) le braille **suit le curseur de revue** et reste aligné sur le texte édité, même quand NVDA attache le braille au contrôle focalisé. En quittant le terminal, le comportement NVDA normal revient. Désactivez pour le comportement par défaut NVDA. Indisponible sur l’écran de connexion sécurisé, ou quand le braille ne suit que la **sortie parole**.
- **Routage dans les champs d’édition :** **normal** transmet la touche à NVDA ; **émuler les flèches** envoie Début/Fin ou Gauche/Droite répétées pour placer le curseur sous la cellule routée ( **bips** optionnels). S’applique en vue braille habituelle, avec la **focalisation** sur le curseur système, dans un **terminal** ou un champ **texte éditable**.
- **Annoncer le caractère lors du routage du curseur braille :** après **routage**, l’extension annonce le **caractère sous le curseur de routage** selon les règles de symboles NVDA. Sur **NVDA 2024.4+**, cette case est **désactivée** au profit de NVDA **Braille → Annoncer le caractère lors du positionnement du curseur de routage dans le texte**.
- **Interruption parole pour commandes inconnues :** pour les touches d’**afficheur** **sans commande assignée**, contrôle si NVDA **arrête la parole**. **Coché** (défaut) : les touches non assignées interrompent la parole. **Décoché** : elles ne l’interrompent pas. Ne s’applique pas à la **saisie** braille, aux touches volume, à l’émulation de modificateurs, ni au défilement ligne quand la règle d’interruption ci-dessus le permet.
- **Configuration clavier braille :** affichée seulement si le profil définit des **dispositions clavier** (tous les afficheurs ne le font pas).
- **Outils Unicode** (à assigner dans **Touches de commandes**) : sur **texte sélectionné** dans une page web s’il y a une sélection ; sinon sur le texte au **curseur de revue**. Conversion texte ↔ braille Unicode et braille Unicode ↔ numéros de points.
- **Informations sur le caractère** (à assigner) : au curseur de revue, nom Unicode, symbole parole, cellules braille et bases numériques ; double appui pour un bloc consultable.

### Tables braille

- **Listes de rotation :** vos listes **entrée** et **sortie** sont des **noms dans l’ordre, séparés par des virgules**. Les commandes **table suivante/précédente** parcourent cet ordre (assignez-les dans **Touches de commandes** si le profil ne le fait pas). **Les tables personnalisées Braille Extender ne figurent pas ici** — choisissez-les uniquement dans le dialogue des tables personnalisées.
- **Ligne automatique :** sur **NVDA 2025.1+**, vous pouvez inclure des entrées **automatiques** ; l’extension les résout avec les tables par défaut selon la langue NVDA. Sur NVDA plus ancien, **auto** n’est pas géré de la même façon — utilisez des fichiers de table explicites.
- **Table d’entrée pour raccourcis :** table séparée optionnelle pour certains raccourcis.
- **Passe Liblouis de sortie supplémentaire :** **deuxième table de sortie** après la principale (tables de votre liste de sortie ; pas les tables personnalisées inactives).
- **Tabulations en espaces :** afficher les tabulations comme des espaces ; **largeur de tabulation** par afficheur actif (**1–42**).
- **Gérer les tables braille personnalisées… :** ouvre le dialogue (voir ci-dessous).

**Dictionnaires de table** (pas dans les onglets paramètres)

Trois niveaux : **Global** (toutes les tables), **Table** (table de **sortie** courante), **Temporaire** (surcharges jusqu’au redémarrage de NVDA). Si un fichier est erroné, ce niveau est ignoré jusqu’à correction.

**Menu NVDA → Braille Extender → Dictionnaires de table** → **Dictionnaire global**, **Dictionnaire de table** ou **Dictionnaire temporaire**.

#### Tables braille personnalisées (NVDA 2024.3+)

Braille Extender peut **stocker et utiliser vos tables** lorsque vous les sélectionnez dans le gestionnaire. Elles s’appliquent à l’**entrée** et à la **sortie** via l’extension (pas via **NVDA → Paramètres → Braille** ni les listes de rotation de l’extension).

**Prérequis**

- **NVDA 2024.3 ou ultérieur**.
- Fichiers **`.utb`**, **`.ctb`** ou **`.tbl`** (pas les fichiers auxiliaires `.cti`, `.dis`, etc.).

**Où ouvrir le gestionnaire**

| Emplacement | Usage |
|-------------|--------|
| **Menu NVDA → Braille Extender → Tables braille personnalisées…** | Dialogue dédié. |
| **Paramètres Braille Extender → Tables braille → Gérer les tables braille personnalisées…** | Même dialogue. |

**Actions possibles**

| Action | Description |
|--------|-------------|
| **Ajouter…** | **Copier une table existante** ou **créer une table vide** avec un fichier minimal. La liste inclut les tables NVDA, celles d’autres extensions et celles déjà stockées. Nom d’affichage, abrégée, entrée/sortie dans le dialogue suivant. |
| **Supprimer** | Supprime les métadonnées et le fichier `.utb` / `.ctb` / `.tbl` après confirmation. |
| **Modifier…** | Ouvre le fichier dans l’éditeur par défaut (dossier utilisateur ci-dessous). |
| **Propriétés…** | Nom, abrégée, utilisation **entrée** et/ou **sortie**. |

Pour **cloner une table déjà gérée**, **Ajouter… → Copier une table existante** et choisissez-la dans la liste.

**Dialogue Ajouter**

- **Copier une table existante** ou **Créer une table vide**.
- **Copier** conserve l’extension source (`.utb`, `.ctb`, `.tbl`).
- **Créer vide** écrit un fichier minimal en **`.utb`**, ou **`.ctb`** si la table est marquée **abrégée** à l’étape propriétés.

**Choisir la table personnalisée active**

En haut du dialogue :

| Contrôle | Effet |
|----------|--------|
| **Table d’entrée personnalisée active** | **Aucune** (défaut) : table d’entrée NVDA normale. Sinon la table choisie pour la saisie braille. |
| **Table de sortie personnalisée active** | **Aucune** : table de sortie NVDA normale. Sinon la table choisie pour la traduction. |

Seules les tables sélectionnées ici sont actives. Elles **n’apparaissent pas** dans **NVDA → Paramètres → Braille** ni dans les listes de rotation Braille Extender, pour que NVDA démarre normalement si l’extension n’est pas chargé.

**OK** applique le choix. Pour arrêter : **Aucune** pour les deux listes (les fichiers restent). Pour supprimer définitivement : **Supprimer** dans le gestionnaire.

**Stockage**

Fichiers et petit fichier de paramètres dans le **dossier de configuration utilisateur NVDA** (**Menu NVDA → Préférences → Général → Ouvrir le répertoire de configuration utilisateur de NVDA**), sous **brailleExtender\customBrailleTables\**.

Après ajout, suppression ou modification, le braille **se met à jour immédiatement**.

**Utilisation au quotidien**

1. Ajoutez la table (**Ajouter… → Copier** ou **créer vide**).
2. Dans **Propriétés**, autorisez **entrée** et/ou **sortie**.
3. Définissez **Table d’entrée** et/ou **de sortie personnalisée active** (ou **Aucune** pour une direction).
4. **OK**. Les nouvelles tables sont sélectionnées automatiquement pour les directions activées à l’ajout.

**Si vous désactivez l’extension**

Le choix de table personnalisée est conservé dans les paramètres Braille Extender pour que NVDA reste sur une table intégrée sûre. En réactivant l’extension, la sélection personnalisée revient.

**Tables d’autres extensions (NVDA 2024.3+)**

Pas besoin de copier dans le dossier Braille Extender. Les tables d’une autre extension (ex. **Experimental braille tables**) ou du scratchpad NVDA fonctionnent comme les tables intégrées : listes de rotation, commandes de table, ou **passe de sortie supplémentaire**. Sur **NVDA 2024.1–2024.2**, seules les tables intégrées NVDA sont prises en charge.

**Fichier de table manquant**

L’extension revient à une table sûre si possible et retire les entrées cassées de vos listes.

### Mise en forme des documents

Braille Extender ne remplace **pas** le dialogue **Mise en forme des documents** de NVDA. L’onglet **Mise en forme des documents** ajoute une couche braille distincte :

- **Par catégorie :** chaque ligne est **Suivre la mise en forme des documents de NVDA**, **activé** ou **désactivé** (voir la description en haut de l’onglet).
- **Mode texte brut** — désactive toute mise en forme de cette couche.
- **Traiter la mise en forme ligne par ligne** — construit le braille ligne à ligne.
- **Lignes de rapport** — une liste par catégorie (attributs de police, emphase, alignement, couleurs, liens, titres, listes, tableaux, coordonnées de cellule, orthographe/grammaire, etc.).
- **Niveau des éléments dans une liste imbriquée** — afficher le niveau d’imbrication en braille.
- **Méthodes…** — affichage par attribut (rien, délégation à la table, points 7/8, balises, remplissage de ligne pour alignements, etc.).
- **Balises…** — chaînes de début/fin pour les méthodes par balises.

Sur **NVDA 2024.4+**, NVDA a aussi des options globales de mise en forme braille ; cet onglet reste le contrôle ligne par ligne de l’extension.

### Présentation des objets

Cet onglet modifie ce qui apparaît sur l’afficheur quand NVDA montre **un objet à la fois** — la ligne récapitulative du contrôle focalisé (bouton, lien, cellule de tableau, etc.). Il ne change **pas** ce que NVDA **dit** ; utilisez **Paramètres NVDA → Présentation des objets** pour la parole.

#### Ordre des propriétés…

**Présentation des objets → Ordre des propriétés…** (dialogue **Ordre des propriétés**) définit **l’ordre des parties**, de gauche à droite sur l’afficheur. Les parties sans contenu pour l’objet courant sont ignorées.

Champs réordonnables (libellés du dialogue) :

- **nom**, **valeur**, **état**, **texte de rôle** (type de contrôle, ex. niveau de titre)
- **description**, **raccourci clavier**, **info de position** (`3/10` en braille, pas « 3 sur 10 »)
- **niveau d’info de position** (niveau hiérarchique, `lv 2`)
- **libellés courants** (ex. « page courante » sur le web)
- **texte indicatif**, **texte des coordonnées de cellule**

**Réinitialiser à l’ordre NVDA par défaut** — comme sans cette extension.

**Réinitialiser l’ordre par défaut de l’extension** — **état** et **coordonnées de cellule** avant **nom** (défaut des nouveaux profils).

**Ce qui suit encore NVDA**

- **Description**, **raccourci** et **position** seulement si les options correspondantes sont activées dans **Paramètres NVDA → Présentation des objets**.
- **Coordonnées de cellule** suivent aussi **Braille Extender → Mise en forme des documents → Coordonnées de cellule**.

Les en-têtes de ligne/colonne de l’application peuvent encore être ajoutés après le résumé principal lorsqu’ils sont disponibles.

#### Éléments sélectionnés

**Éléments sélectionnés** marque un élément **sélectionné** sur la ligne récapitulative :

| Choix | Effet |
|-------|--------|
| **rien** | Pas de marquage supplémentaire |
| **point 7**, **point 8**, ou **points 7 et 8** | Ajoute les points 7 et/ou 8 aux cellules du **nom** |
| **balises** | Pas de caractères de balise sur le nom ; affecte seulement le texte d’état comme ci-dessous |

Si le choix n’est pas **rien** et l’objet a un **nom**, les mots **sélectionné** et **sélectionnable** sont omis du **texte d’état** pour éviter la redondance. La surbrillance **dans le texte courant** suit le paramètre NVDA **afficher la sélection**.

#### Messages braille pour les barres de progression

Quand la valeur d’une barre change, l’extension peut afficher un **court message braille** (la parole est inchangée — utilisez **Paramètres NVDA → Présentation des objets → Mises à jour de la barre de progression** pour la parole) :

| Option | Affichage |
|--------|-----------|
| **désactivé (comportement d’origine)** | Pas de message braille supplémentaire |
| **activé, valeur brute** | Texte de la valeur (défaut) |
| **activé, barre avec ⣿** | Rangée de cellules remplies selon le pourcentage |

#### Signaler les barres de progression en arrière-plan

Les trois choix (**Suivre la mise en forme des documents de NVDA**, **activé**, **désactivé**) décident **quelles fenêtres** peuvent déclencher les messages ci-dessus :

| Choix | Effet |
|-------|--------|
| **Suivre la mise en forme des documents de NVDA** | Suit **Signaler les barres de progression en arrière-plan** NVDA, ou les barres de la fenêtre de travail |
| **activé** | Barres en arrière-plan et au premier plan |
| **désactivé** | Seulement les barres de la fenêtre **au premier plan** |

### Excel

**Paramètres Braille Extender → Excel** contrôle l’affichage braille des cellules **Microsoft Excel** lorsque NVDA peut les lire comme avec les flèches. Ne s’applique **pas** à d’autres tableurs (LibreOffice Calc, feuilles dans le navigateur, etc.).

Si vous utilisiez **Mise en forme des documents → Formule de cellule**, l’option est déplacée ici. À la mise à jour, votre choix précédent est copié dans **Excel → Signaler les formules de cellule en braille**.

#### Signaler les formules de cellule en braille

Si **coché** (défaut), l’extension peut afficher les **formules** en braille, pas seulement la valeur visible. Si **décoché**, comportement braille Excel standard NVDA sans ligne formule de cette extension.

Sans l’extension, NVDA affiche souvent **frml** pour une cellule avec formule. Avec **Cellule focalisée uniquement** (ci-dessous), vous gardez la ligne cellule habituelle et la **formule complète** s’ajoute — vous lisez la formule, pas seulement **frml**.

#### Vue braille

Contrôle **combien de la feuille** apparaît sur l’afficheur :

| Choix | Affichage |
|-------|-----------|
| **Cellule focalisée uniquement** (défaut) | La cellule courante, plus sa formule si présente. Comme le braille Excel NVDA habituel. |
| **Plage de ligne sur une ligne** | Une **portion de la ligne** autour de la cellule — pas toute la ligne de la feuille. Nombre de cellules de chaque côté : **Cellules de chaque côté de la focalisation (ligne de plage ligne/colonne)** (défaut **9**). La ligne peut être plus courte : du premier au dernier **non vide** dans la fenêtre. |
| **Plage de colonne sur une ligne** | Idem pour la **colonne** autour de la cellule (plage limitée, pas toute la colonne). |

Les vues ligne/colonne servent à parcourir les **cellules voisines** sans déplacer la focalisation cellule par cellule.

Vous pouvez aussi changer la **Vue braille** au clavier dans Excel : **NVDA → Préférences → Touches de commandes**, assignez **Parcourir la vue braille Excel (cellule focalisée, plage de ligne ou de colonne sur une ligne)** (catégorie **Braille Extender**). Pas de raccourci par défaut ; chaque appui passe par **Cellule focalisée uniquement**, **Plage de ligne sur une ligne**, **Plage de colonne sur une ligne**, puis recommence. La commande ne fonctionne que si **Signaler les formules de cellule en braille** est activé.

En vue **Cellule focalisée uniquement**, le défilement braille est comme NVDA (votre position sur la ligne est conservée entre cellules). En **Plage de ligne sur une ligne** ou **Plage de colonne sur une ligne**, la **cellule focalisée** reste à **gauche** de l’afficheur en changeant de cellule.

#### Formules sur la ligne de plage (ligne ou colonne)

S’applique seulement si **Vue braille** est **Plage de ligne sur une ligne** ou **Plage de colonne sur une ligne** :

| Choix | Signification |
|-------|----------------|
| **Cellule focalisée uniquement** (défaut) | Les voisines montrent leurs **valeurs** ; la cellule **focalisée** peut encore montrer sa formule. |
| **Chaque cellule de la ligne** | Valeurs **et** formules pour chaque cellule de la ligne. |
| **Valeurs uniquement (pas de formules)** | Valeurs seulement ; formules masquées sur l’aperçu. |

#### Cellules de chaque côté de la focalisation (ligne de plage ligne/colonne)

En vue **Plage de ligne sur une ligne** ou **Plage de colonne sur une ligne**, nombre maximal de cellules **à gauche et à droite** (ligne) ou **au-dessus et en dessous** (colonne). Défaut **9** (jusqu’à **19** positions : 9 + cellule + 9). De **0** à **50**.

La ligne est en général **plus courte** que ce maximum : du premier au dernier **non vide** dans la fenêtre. Les cellules **vides entre** deux cellules avec contenu apparaissent comme espaces vides.

#### Séparateur entre cellules sur la ligne

Texte **entre** chaque cellule sur une ligne ligne ou colonne. Défaut : espace, barre verticale, espace : ` | `. Modifiable (ex. ` - ` ou `, `).

#### Préfixes de ligne (plage ligne) et de colonne (plage colonne)

En vue **Plage de ligne sur une ligne** ou **Plage de colonne sur une ligne**, court **préfixe** au **début** de la ligne braille, **avant** l’adresse de la cellule courante. NVDA ajoute **un espace** après le préfixe — ne mettez **pas** d’espace final dans le paramètre.

| Champ | Défaut (français) | Rôle |
|-------|-------------------|------|
| **Préfixe de ligne (plage ligne)** | `lig` | Lignes de plage de ligne (ex. `lig A2: Bonjour | …`) |
| **Préfixe de colonne (plage colonne)** | `col` | Lignes de plage de colonne (ex. `col A2: Bonjour | …`) |

Laissez vide pour le **défaut traduit** selon la langue NVDA. Saisissez votre libellé court (ex. `L` ou `Ln`) si vous préférez.

#### Aspect d’une ligne ligne ou colonne

Exemples (séparateur et préfixes par défaut) :

- Ligne **2**, vous êtes en **A2** avec `Bonjour`, **B2–F2** vides, **99** en **G2** :  
  `lig A2: Bonjour |  |  |  |  |  | 99`
- Le préfixe (**`lig`** ou **`col`** par défaut en français) indique plage de ligne ou de colonne ; l’**adresse courante** (`A2:`) suit le préfixe et un espace.
- Seule la cellule **courante** a son adresse sur la ligne (ex. `A2: Bonjour`). Les autres n’affichent que la valeur (ou rien si vide).
- Les cellules **vides entre** deux cellules avec contenu : ` |  | `.
- Les **en-têtes de ligne/colonne** du classeur (libellés supplémentaires NVDA pour la cellule courante) apparaissent après la partie de la **cellule courante**, pas après chaque voisine.

#### Touches de routage sur une ligne ligne ou colonne

En vue **Plage de ligne sur une ligne** ou **Plage de colonne sur une ligne**, chaque partie de la ligne correspond à **une cellule** :

- **Routage** sur la valeur de la **cellule courante** (ex. sous `Bonjour` dans `A2: Bonjour`) pour **éditer** la cellule, comme le routage Excel NVDA habituel.
- **Routage** sur la valeur d’une **voisine** (ou sur un espace vide) pour **aller** à cette cellule.

Vous pouvez ainsi parcourir la ligne ou la colonne depuis l’afficheur sans flèches cellule par cellule.

#### Cellules fusionnées

Si plusieurs colonnes ou lignes sont **fusionnées** :

- La **valeur** s’affiche **une fois** au début de la zone fusionnée sur la ligne.
- Les autres positions de la fusion sont des **emplacements vides** sur la ligne ; le routage y mène quand même à la **cellule fusionnée**.
- La **cellule courante** montre l’adresse fusionnée complète si NVDA la rapporte ainsi (ex. `B2 through D2`), avec valeur ou formule partout dans la fusion.

### Documents virtuels (tableaux web)

Quand vous lisez une **page web en mode navigation** (la page est chargée et vous vous déplacez avec les flèches), et que le curseur est **dans un tableau**, Braille Extender peut afficher **toute la ligne sur une seule ligne braille** au lieu d’une seule cellule. C’est le même principe que la **plage de ligne sur une ligne** d’Excel, mais pour les **tableaux sur le web** (et documents similaires en mode navigation — pas pour les feuilles Excel ; voir [Excel](#excel)).

Ouvrez **Paramètres Braille Extender → Documents virtuels**.

#### Afficher la ligne de tableau entière sur une ligne braille

Si cette case est **cochée** (défaut), chaque ligne de tableau est disposée horizontalement sur l’afficheur braille. Si elle est **décochée**, les tableaux utilisent le braille NVDA habituel (une cellule à la fois).

#### Aspect d’une ligne de tableau

Avec les marqueurs par défaut, une ligne peut ressembler à :

`tb(4,10)(| Nom | Âge | Ville |)`

- **tb(4,10)** — sur la **première ligne** du tableau seulement : le tableau compte 4 lignes et 10 colonnes. Sur les lignes suivantes, cette partie n’est pas répétée.
- **Début de ligne de tableau** (défaut `(| `) — début de la ligne.
- **Séparateur entre cellules** (défaut ` | `) — entre chaque cellule.
- **Fin de ligne de tableau** (défaut ` |)`) — fin de la ligne.
- **tb end** — sur la **dernière ligne** du tableau seulement, après le marqueur de fin : indique que le tableau se termine ici.

La **cellule où vous êtes** est marquée par le curseur braille habituel. Les autres cellules de la ligne n’affichent que leur texte (pas de numéros de ligne ou de colonne supplémentaires sur chaque cellule, sauf si NVDA les inclut déjà dans le contenu de la cellule).

Les cellules vides occupent quand même une place sur la ligne (vous voyez le séparateur sans texte entre). Les **en-têtes de ligne ou de colonne** de la page, lorsque NVDA les fournit, suivent les mêmes règles qu’en mode navigation habituel pour la cellule focalisée.

#### Marqueurs personnalisés

Vous pouvez modifier les trois champs de texte dans **Documents virtuels** si les valeurs par défaut ne vous conviennent pas :

| Paramètre | Défaut (anglais) | Rôle |
|-----------|------------------|------|
| **Séparateur entre cellules** | espace, barre verticale, espace | Entre chaque cellule sur la ligne |
| **Début de ligne de tableau** | parenthèse ouvrante, barre verticale, espace | Début de la ligne |
| **Fin de ligne de tableau** | espace, barre verticale, parenthèse fermante | Fin de la ligne |

Sur l’afficheur, les défauts s’écrivent ` | `, `(| ` et ` |)`.

Utilisez des libellés courts que vous reconnaissez sur un petit afficheur. Les changements s’appliquent dès l’enregistrement des paramètres.

#### Touches de routage sur une ligne de tableau

Sur les afficheurs avec **touches de routage** (boutons au-dessus ou en dessous des cellules braille) :

**Sur le texte d’une cellule**

- Appuyez sur une touche de routage sur le **contenu** d’une cellule pour **déplacer le curseur** à ce caractère dans la page, comme en mode navigation habituel (y compris suivre un lien ou activer un bouton si vous routez dessus).

**Sur les séparateurs et marqueurs de ligne**

- Appuyez sur une touche de routage sur le **séparateur entre deux cellules** (par défaut espace, barre verticale, espace) : NVDA affiche un **court message** avec la **colonne**, par exemple **colonne 3 (ligne 2)**.
- Appuyez sur une touche de routage sur le **début de la ligne** (par défaut `(| `) ou la **fin de la ligne** (par défaut ` |)`) : NVDA affiche un **court message** avec la **ligne**, par exemple **ligne 2**.

Le message apparaît brièvement sur l’afficheur braille (NVDA peut aussi le dire à voix haute selon vos paramètres). Ensuite, le curseur se place dans la **cellule voisine** du marqueur que vous avez pressé, pour que vous restiez orienté dans le tableau.

#### Cellules fusionnées

Quand une cellule **couvre plusieurs colonnes ou lignes** :

- Son **texte** s’affiche **une fois** au début de cette cellule sur la ligne (pas répété dans chaque colonne de la fusion).
- Les autres colonnes couvertes par la fusion apparaissent comme des **espaces vides** sur la ligne, mais une touche de routage y mène quand même à la **même cellule fusionnée**.
- Les messages sur les séparateurs utilisent des **plages** lorsque c’est utile, par exemple **colonnes 1-3 (ligne 2)** ou **lignes 2-4**, pour indiquer l’étendue de la fusion.

#### Quand cette fonction est active

- Le curseur doit être **dans un tableau** sur une page en **mode navigation** (lecture web habituelle avec Firefox, Chrome, Edge, etc.).
- Elle **ne remplace pas** le braille Excel (voir [Excel](#excel)).
- Hors tableaux, ou si **Afficher la ligne de tableau entière sur une ligne braille** est désactivé, le braille se comporte comme d’habitude.

### Représentation des caractères non définis

Les caractères **non définis** dans la table de sortie active (dont beaucoup d’**emoji**) utilisent la **méthode** choisie : **comportement de la table**, cellule **1–8** ou **1–6**, **vide**, **motif de points** personnalisé (ex. `6-123456`), **point d’interrogation**, **signe** personnalisé (ex. `??`), **hex** (style table, **HUC8**, **HUC6**), **décimal**, **octal**, **binaire**.

**Descriptions :** description de caractère optionnelle, **étendue**, **étendue complète**, ligne de **taille** optionnelle, **données Unicode** en dernier recours, liste **d’exclusion** (codes ou plages) pour ignorer les plages trop verbeuses.

**Priorité :** règles de table et **dictionnaires de table** avant les descriptions ; descriptions avant le motif générique non défini.

Plus sur **HUC** : [danielmayr.at/huc](https://danielmayr.at/huc/)

### Mode de saisie avancée

**Onglet paramètres :** signe d’échappement pour saisie numérique/Unicode et **quitter après un caractère**.

**Dialogue menu :** **Menu NVDA → Braille Extender → Dictionnaire du mode de saisie avancée…** — abréviations par table d’entrée (séparé des dictionnaires de table).

Basculez le **mode de saisie avancée** (défauts : **NVDA+Windows+i** ou **⡊+espace**). Pendant l’activation :

- **HUC8 :** saisissez le **motif HUC8 braille Unicode** du caractère ; l’extension attend une séquence **valide et complète**, puis insère le caractère (souvent **environ quatre** cellules pour les symboles ; parfois plus — voir [HUC](https://danielmayr.at/huc/)). Fonctionne pour **emoji** et autres points de code pris en charge.
- **Bases numériques :** après le signe **d’échappement**, **⠭** ou **⠓** (hex), **⠙** (décimal), **⠕** (octal), **⠃** (binaire), chiffres, puis **Espace**.
- **Abréviations :** dans le **dictionnaire du mode de saisie avancée** (dialogue menu ; une entrée par abréviation et table). Même abréviation ajoutée deux fois : le nouveau texte **remplace** l’ancien. Expansion : **abréviation + Espace**.

**Saisie HUC6** non implémentée.

| Caractère | HUC8 | Hex | Décimal | Octal | Binaire |
|-----------|------|-----|---------|-------|--------|
| 👍 pouce levé | ⣭⢤⡙ | 1F44D | 128077 | 372115 | 11111010001001101 |
| 😀 visage rieur | ⣭⡤⣺ | 1F600 | 128512 | 373000 | 11111011000000000 |
| 🍑 pêche | ⣭⠤⠕ | 1F351 | 127825 | 371521 | 11111001101010001 |
| 🌊 vague | ⣭⠤⠺ | 1F30A | 127754 | 371412 | 11111001100001010 |

### Mode unimanuel

Composez une cellule en plusieurs étapes — utile si vous tapez d’une seule main. Dans **Paramètres Braille Extender**, les trois méthodes apparaissent dans cet ordre : **Remplir une cellule en deux étapes d’un seul côté**, **Remplir une cellule en deux étapes des deux côtés**, **Remplir une cellule point par point**. Basculez avec **NVDA+Windows+h** (souvent **⡂+espace** sur les afficheurs pris en charge). Si la méthode enregistrée est inconnue, l’extension annonce **non prise en charge** et efface toute cellule partiellement saisie.

#### Un seul côté (deux étapes sur une moitié ; Espace = moitié vide)

Première étape : points **1–2–3–7**. Deuxième : **4–5–6–8**. **Espace** = « cette moitié est vide ». **Espace deux fois** = cellule entièrement vide.

- **⠛ :** **1–2** puis **1–2**, ou **4–5** puis **4–5**
- **⠃ :** **1–2** puis **Espace**, ou **4–5** puis **Espace**
- **⠘ :** **Espace** puis **1–2**, ou **Espace** puis **4–5**

#### Les deux côtés (moitié gauche, puis droite)

Tapez la moitié **gauche**, puis la **droite**. Si un côté est vide, appuyez **deux fois** sur les mêmes points, ou saisissez le côté non vide en **deux** étapes.

- **⠛ :** **1–2**, puis **4–5**
- **⠃ :** **1–2** puis **1–2**, ou **1** puis **2**
- **⠘ :** **4–5** puis **4–5**, ou **4** puis **5**

#### Point par point (bascule)

Chaque touche **inverse** un point. **Espace** quand la cellule convient.

**⠛** peut se construire : **1–2** puis **4–5** puis Espace ; ou **1–2–3**, point **3** à nouveau pour corriger, puis **4–5**, Espace ; etc.

### Mode historique de parole

**Ne pas confondre avec le raccourci NVDA de bascule du mode braille (`NVDA+Alt+t`).**

Dans NVDA actuel (voir **Référence des commandes → Braille** et **Aide à la saisie**) :

- **`NVDA+Alt+t`** — **Basculer le mode braille** (documenté depuis **NVDA 2024.2**, avec le mode **sortie parole** : le braille peut refléter ce que NVDA annonce). NVDA fait défiler ses modes braille, dont **affichage** et **sortie parole**. Ce n’est **pas** la **liste d’historique de parole** et le **routage** de Braille Extender.

**Ce que fait Braille Extender**

Quand le **Mode historique de parole** est **activé**, l’extension **enregistre ce que NVDA annonce** en lignes de texte consultables, utilise le **défilement par ligne** pour parcourir la liste, et **remplace la ligne braille** par ces lignes au lieu de la focalisation ou de la revue habituelles. Désactiver le mode restaure le braille normal.

- **Assigner une commande :** pas de raccourci bureau obligatoire — **Touches de commandes → Braille Extender →** *Activer ou désactiver le mode historique de parole de Braille Extender…* De nombreux profils utilisent une **commande** comme **⡞+espace** ; voir **Gestes pour cet afficheur…**.
- **Conflit :** évitez **`NVDA+Alt+t`** pour cette commande de l’extension sauf si vous voulez **remplacer** la commande NVDA de bascule du mode braille.
- **Pendant la consultation :** la parole est capturée en **texte seul** (pas de sons dans la liste) ; les commandes avant/arrière ligne parcourent l’historique en ce mode.
- **Limite :** nombre de lignes conservées (maximum très élevé dans les paramètres).
- **Numéroter les entrées :** chaque ligne est préfixée par **`#`** et le **numéro** (zéros en tête pour largeur uniforme), puis **`:`** et le texte — ex. **`#3:`** ou **`#0003:`** selon la limite.
- **Annoncer les entrées :** lire la ligne à voix haute en se déplaçant dans l’historique.
- **Routage :** la touche de routage **la plus à gauche** copie la ligne courante ; la **plus à droite** ouvre un texte **consultable** ; les **touches du milieu** avancent ou reculent dans la liste selon le côté de l’afficheur.

### Rotor

Le rotor change la **catégorie de navigation rapide / revue** active. Catégories : **navigation texte**, **sélection**, **objet / revue**, **liens** (visités/non visités), **repères**, **titres** (par niveau), listes, contrôles de formulaire, **tableaux**, **mise en forme identique/différente**, listes **tables entrée/sortie**, etc.

- **Paramètres :** activer/désactiver chaque catégorie et définir l’**ordre principal**. Seuls les éléments **activés** apparaissent au cycle.
- **Catégories visibles :** dans les vues de type **mode navigation** (nombreuses pages web, documents similaires, certaines vues d’applications avec navigation rapide), l’extension **interroge NVDA** ; les types qui échoueraient toujours (ex. certains sauts de **mise en forme** dans **Word**) sont **masqués**.
- **Commandes :** assignez **élément rotor suivant/précédent** et **jeu rotor suivant/précédent** dans **Touches de commandes** ; les profils peuvent déjà les lier.

### Défilement automatique

Quand le **défilement automatique** est **activé**, l’afficheur **avance seul** sur un minuteur en vue braille habituelle. En passant à une autre vue (ex. historique de parole), le défilement automatique **se met en pause** jusqu’au retour.

- **Délai :** stocké **par modèle d’afficheur**, entre environ **0,2 et 42 secondes** entre pas (défaut environ **3 secondes**).
- **Touches plus rapide / plus lent :** chaque appui modifie le délai d’un pas configurable (environ **25 ms** à **7 s** par pas).
- **Ajuster au contenu :** le délai peut varier selon **la part de la ligne courante** visible sur l’afficheur.
- **Ignorer les lignes vides :** ignorer les lignes vides pendant le défilement automatique.
- **Bips** à l’activation ou la désactivation.

### Libellés de rôles

Si **Utiliser des libellés de rôles personnalisés** est coché, vous pouvez modifier les libellés **rôle**, **repère** et **états positifs / négatifs** par langue (stockés avec les autres paramètres Braille Extender). Si décoché, les libellés NVDA par défaut s’appliquent.

### Avancé

- **Éviter les problèmes de position du curseur avec certains caractères comme les sélecteurs de variation** — améliore l’alignement braille à côté de certains caractères Unicode.
- **Forcer l’actualisation de la région braille liée à l’objet au premier plan** — met à jour l’afficheur quand le **nom** de l’élément focalisé change souvent (minuteries, compteurs, titres de fenêtre).

---

## Fonctionnalités principales

- Recharger deux **afficheurs braille favoris** par raccourci.
- **Terminaux :** le braille peut suivre le **curseur de revue** pendant l’édition (PuTTY, PowerShell, cmd, bash, …).
- **Défilement automatique** avec réglages et options lignes vides.
- **Plusieurs tables entrée/sortie** et sélection **automatique** sur NVDA 2025.1+.
- **Excel :** aperçu **ligne ou colonne sur une ligne braille** avec routage (voir [Excel](#excel)).
- **Tableaux web en mode navigation :** **ligne de tableau entière sur une ligne braille** avec messages sur les séparateurs (voir [Documents virtuels (tableaux web)](#documents-virtuels-tableaux-web)).
- **Tables braille personnalisées** (ajout, copie, édition) sur NVDA 2024.3+ ; activation uniquement depuis le dialogue des tables personnalisées (**Aucune** = désactivé).
- **Points 7/8**, **balises** et remplissage de ligne pour structure et attributs (**Méthodes** de mise en forme des documents).
- **Masquer/afficher les points 7 et 8** — commande dans **Touches de commandes** (pas une case Avancé).
- **Seconde passe de traduction** (table de sortie optionnelle après la principale).
- **Tabulations en espaces** ; **inversion** des touches de défilement.
- **Dire la ligne courante** au défilement (coordonner avec les options parole braille NVDA).
- Outils **braille Unicode** et **description de cellule** pour la sélection.
- **Verrouiller** le clavier braille ; **verrouiller les modificateurs** depuis le braille.
- **Lancements rapides** et **dictionnaires de table** (menu NVDA → Braille Extender).
- Saisie **unimanuelle** ; **caractères non définis** (dont emoji) ; **saisie avancée** et abréviations.
- **Mode historique de parole** ; cartes de **commandes étendues** pour l’afficheur lorsque des profils existent.

---

## Commandes et profils

- **Clavier :** sous **Touches de commandes → Catégorie : Braille Extender**. **Gestes pour cet afficheur…** montre les liaisons du **profil braille actuel** (y compris touches propres à l’afficheur).
- **Afficheur braille :** certains afficheurs ont une carte de commandes prédéfinie. Sinon, assignez les commandes comme toute commande NVDA.
- **Pas dans les onglets paramètres** (menu ou Touches de commandes uniquement) : masquer/afficher points 7–8, verrouiller clavier braille, verrouiller modificateurs, lancements rapides, dictionnaires de table, dictionnaire saisie avancée, gestionnaire tables personnalisées, aperçu de table, outils Unicode, informations caractère, etc. — recherchez **Braille Extender** dans Touches de commandes.

---

## Retours et contributions

Signalements de bogues, suggestions et pull requests sont les bienvenus sur [GitHub — BrailleExtender](https://github.com/aaclause/BrailleExtender/). Si vous modifiez du texte visible ou le comportement, mettez à jour ce guide et les traductions que vous maintenez.

Le **code source**, la compilation et les outils de développement sont décrits sur le dépôt GitHub (pas dans ce guide utilisateur).

---

## Remerciements

- **Copyright :** © 2016-2026 André-Abush Clause et autres contributeurs — voir [page du projet](https://github.com/aaclause/BrailleExtender/).

### Traducteurs

- **Arabe :** Ikrami Ahmad  
- **Chinois (Taïwan) :** 蔡宗豪 Victor Cai &lt;surfer0627@gmail.com&gt;  
- **Croate :** Zvonimir Stanečić &lt;zvonimirek222@yandex.com&gt;  
- **Danois :** Daniel Gartmann &lt;dg@danielgartmann.dk&gt;  
- **Anglais et français :** Sof &lt;hellosof@gmail.com&gt;, Joseph Lee, André-Abush Clause &lt;dev@andreabc.net&gt;, Oreonan &lt;corentin@progaccess.net&gt;  
- **Allemand :** Adriani Botez, Karl Eick, Rene Linke, Jürgen Schwingshandl  
- **Hébreu :** Shmuel Naaman, Afik Sofer, David Rechtman, Pavel Kaplan  
- **Italien :** Simone Dal Maso, Fabrizio Marini  
- **Persan :** Mohammadreza Rashad  
- **Polonais :** Zvonimir Stanečić, Dorota Krać  
- **Russe :** Zvonimir Stanečić, Pavel Kaplan, Artem Plaksin  
- **Espagnol :** Eric Duarte Quintanilla  
- **Turc :** Umut Korkmaz  
- **Ukrainien :** VovaMobile  

### Code et tiers

- **Fonction Mode historique de parole :** Emil Hesmyr &lt;emilhe@viken.no&gt;  
- **Maintenance / nettoyage :** Joseph Lee &lt;joseph.lee22590@gmail.com&gt;  
- **Attribra** (tiers) : Copyright © 2017 Alberto Zanella — [attribra](https://github.com/albzan/attribra/)  

Merci aussi à Daniel Cotto, Daniel Mayr, Dawid Pieper, Corentin, Louis, et à tous ceux qui ont fait des retours.
